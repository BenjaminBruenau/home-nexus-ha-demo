# device_simulator.py
import os
import time
import json
import threading
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import uvicorn

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("device_simulator")

# MQTT / HA prefixes
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_PREFIX = "home/mock"
DISCOVERY_PREFIX = "homeassistant"

# Devices
DEFAULT_DEVICES = [
    {
        "object_id": "temp_livingroom",
        "component": "sensor",
        "name": "Temperature Livingroom",
        "unique_id": "mock_temp_livingroom",
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "state_topic": f"{MQTT_PREFIX}/temp_livingroom/state",
    },
    {
        "object_id": "motion_livingroom",
        "component": "binary_sensor",
        "name": "Motion Livingroom",
        "unique_id": "mock_motion_livingroom",
        "device_class": "motion",
        "state_topic": f"{MQTT_PREFIX}/motion_livingroom/state",
    },
    {
        "object_id": "door_front",
        "component": "binary_sensor",
        "name": "Door Front",
        "unique_id": "mock_door_front",
        "device_class": "door",
        "state_topic": f"{MQTT_PREFIX}/door_front/state",
    },
    {
        "object_id": "switch_coffee",
        "component": "switch",
        "name": "Coffee Switch",
        "unique_id": "mock_switch_coffee",
        "state_topic": f"{MQTT_PREFIX}/switch_coffee/state",
        "command_topic": f"{MQTT_PREFIX}/switch_coffee/set",
    },
]

# In-memory state
STATE = {
    "temp_livingroom": 21.0,
    "motion_livingroom": False,
    "door_front": False,
    "switch_coffee": False,
}

# Threading event so we know when MQTT is connected
connected_event = threading.Event()

client = mqtt.Client()


def on_connect(c, userdata, flags, rc, properties=None):
    # rc==0 success
    if rc == 0:
        log.info("MQTT connected to %s:%s (rc=%s)", MQTT_BROKER, MQTT_PORT, rc)
        connected_event.set()
        # subscribe to command topics so we can react to set messages
        for d in DEFAULT_DEVICES:
            if "command_topic" in d:
                client.subscribe(d["command_topic"], qos=1)
                log.info("Subscribed to command topic: %s", d["command_topic"])
    else:
        log.warning("MQTT connection returned code %s", rc)


def on_disconnect(c, userdata, rc, properties=None):
    log.warning("MQTT disconnected (rc=%s)", rc)
    connected_event.clear()


def on_message(c, userdata, msg):
    try:
        t = msg.topic
        payload = msg.payload.decode("utf-8")
        log.info("MQTT message received on %s: %s", t, payload)
        # map known set topics -> update STATE
        for d in DEFAULT_DEVICES:
            if d.get("command_topic") == t:
                # turn 'ON'/'OFF' or JSON boolean or 'true'/'false'
                val = payload.strip().upper()
                if val in ("ON", "OFF"):
                    new = True if val == "ON" else False
                else:
                    # try parse JSON/number
                    try:
                        new = json.loads(payload)
                    except Exception:
                        # fallback string
                        new = payload
                key = d["object_id"].replace(d["component"] + "_", "") if False else d["object_id"]
                # Normalize key names to our STATE keys
                # Our STATE uses same keys as object_id in this script
                if key in STATE:
                    STATE[key] = new
                    publish_state(key)
                    log.info("Updated state %s -> %s (via command topic)", key, new)
                else:
                    log.warning("Unknown state key for topic %s", t)
    except Exception as e:
        log.exception("Error handling incoming message: %s", e)


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message


def ensure_mqtt_connected():
    """Attempt to connect with retries and wait for connected_event."""
    backoff = 1
    while True:
        try:
            log.info("Attempting MQTT connect to %s:%s", MQTT_BROKER, MQTT_PORT)
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            # wait up to 10s for on_connect to set the event
            if connected_event.wait(timeout=10):
                log.info("MQTT connection established and confirmed.")
                return
            else:
                log.warning("MQTT connect attempt timed out waiting for on_connect; will retry.")
                client.loop_stop()
        except Exception as e:
            log.exception("MQTT connect error: %s", e)
        time.sleep(backoff)
        backoff = min(backoff * 2, 30)


def publish_state(sensor_id):
    topic = f"{MQTT_PREFIX}/{sensor_id}/state"
    value = STATE[sensor_id]
    if isinstance(value, bool):
        payload = "ON" if value else "OFF"
    else:
        payload = str(value)
    client.publish(topic, payload, qos=1, retain=True)
    log.info("Published state %s -> %s on %s", sensor_id, payload, topic)


def publish_discovery():
    for d in DEFAULT_DEVICES:
        discovery_topic = f"{DISCOVERY_PREFIX}/{d['component']}/{d['object_id']}/config"
        payload = {
            "name": d["name"],
            "unique_id": d["unique_id"],
            "device": {
                "identifiers": ["home_nexus_mock"],
                "name": "Home Nexus Mock Devices",
                "model": "simulator",
                "manufacturer": "home-nexus",
            },
        }
        # include state/command/topic specifics
        if "device_class" in d:
            payload["device_class"] = d["device_class"]
        if "unit_of_measurement" in d:
            payload["unit_of_measurement"] = d["unit_of_measurement"]
        if "state_topic" in d:
            payload["state_topic"] = d["state_topic"]
        if "command_topic" in d:
            payload["command_topic"] = d["command_topic"]
        # publish retained discovery messages
        client.publish(discovery_topic, json.dumps(payload), qos=1, retain=True)
        log.info("Published discovery to %s: %s", discovery_topic, payload)

    # publish initial states (give HA a moment)
    time.sleep(1)
    for k in STATE.keys():
        publish_state(k)


# FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MQTT before the app starts serving requests
    ensure_mqtt_connected()
    # Publish discovery after connection
    publish_discovery()
    # Start background periodic publisher
    stop_event = threading.Event()
    t = threading.Thread(target=periodic_publish, args=(stop_event,), daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        client.loop_stop()
        client.disconnect()


app = FastAPI(lifespan=lifespan)


class SetReq(BaseModel):
    value: object


@app.get("/sensors")
def list_sensors():
    return STATE


@app.post("/sensors/{sensor_id}/set")
def set_sensor(sensor_id: str, req: SetReq):
    if sensor_id not in STATE:
        return {"error": "unknown sensor"}, 404
    STATE[sensor_id] = req.value
    publish_state(sensor_id)
    return {"ok": True, "id": sensor_id, "value": req.value}


@app.post("/scenarios/{name}/run")
def run_scenario(name: str):
    if name == "morning":
        STATE["motion_livingroom"] = True
        STATE["temp_livingroom"] = 22.0
        STATE["switch_coffee"] = True
        publish_state("motion_livingroom")
        publish_state("temp_livingroom")
        publish_state("switch_coffee")
        return {"scenario": "morning", "status": "started"}
    return {"error": "unknown"}, 404


def periodic_publish(stop_event: threading.Event):
    while not stop_event.is_set():
        # simple temperature drift simulation
        STATE["temp_livingroom"] += (0.1 if STATE["switch_coffee"] else -0.02)
        publish_state("temp_livingroom")
        # motion decays to false
        if STATE["motion_livingroom"]:
            STATE["motion_livingroom"] = False
            publish_state("motion_livingroom")
        stop_event.wait(10)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
