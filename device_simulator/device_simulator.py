"""
This small app does two things:
1. Publishes Home Assistant MQTT Discovery payloads for demo sensors and switches so Home Assistant auto-creates entities.
2. Publishes periodic sensor state updates and exposes a REST endpoint to trigger scenarios like `morning`, `away`, etc.
"""
import os
import time
import json
import threading
from fastapi import FastAPI
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import uvicorn
import yaml

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_PREFIX = 'home/mock'
DISCOVERY_PREFIX = 'homeassistant'

# demo devices config (you can add more in simulator_config.yaml)
DEFAULT_DEVICES = [
    {
        'object_id': 'temp_livingroom',
        'component': 'sensor',
        'name': 'Temperature Livingroom',
        'unique_id': 'mock_temp_livingroom',
        'device_class': 'temperature',
        'unit_of_measurement': '°C',
        'state_topic': f'{MQTT_PREFIX}/temp_livingroom/state'
    },
    {
        'object_id': 'motion_livingroom',
        'component': 'binary_sensor',
        'name': 'Motion Livingroom',
        'unique_id': 'mock_motion_livingroom',
        'device_class': 'motion',
        'state_topic': f'{MQTT_PREFIX}/motion_livingroom/state'
    },
    {
        'object_id': 'door_front',
        'component': 'binary_sensor',
        'name': 'Door Front',
        'unique_id': 'mock_door_front',
        'device_class': 'door',
        'state_topic': f'{MQTT_PREFIX}/door_front/state'
    },
    {
        'object_id': 'switch_coffee',
        'component': 'switch',
        'name': 'Coffee Switch',
        'unique_id': 'mock_switch_coffee',
        'state_topic': f'{MQTT_PREFIX}/switch_coffee/state',
        'command_topic': f'{MQTT_PREFIX}/switch_coffee/set'
    }
]

# In-memory state
STATE = {
    'temp_livingroom': 21.0,
    'motion_livingroom': False,
    'door_front': False,
    'switch_coffee': False
}

client = mqtt.Client()

app = FastAPI()

class SetReq(BaseModel):
    value: object

@app.on_event('startup')
def startup():
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    publish_discovery()
    threading.Thread(target=periodic_publish, daemon=True).start()

@app.get('/sensors')
def list_sensors():
    return STATE

@app.post('/sensors/{sensor_id}/set')
def set_sensor(sensor_id: str, req: SetReq):
    if sensor_id not in STATE:
        return {'error': 'unknown sensor'}, 404
    STATE[sensor_id] = req.value
    publish_state(sensor_id)
    return {'ok': True, 'id': sensor_id, 'value': req.value}

@app.post('/scenarios/{name}/run')
def run_scenario(name: str):
    if name == 'morning':
        STATE['motion_livingroom'] = True
        STATE['temp_livingroom'] = 22.0
        STATE['switch_coffee'] = True
        publish_state('motion_livingroom')
        publish_state('temp_livingroom')
        publish_state('switch_coffee')
        return {'scenario': 'morning', 'status': 'started'}
    return {'error': 'unknown'}, 404


def publish_discovery():
    for d in DEFAULT_DEVICES:
        discovery_topic = f"{DISCOVERY_PREFIX}/{d['component']}/{d['object_id']}/config"
        payload = {
            'name': d['name'],
            'unique_id': d['unique_id'],
            'device': {
                'identifiers': ['home_nexus_mock'],
                'name': 'Home Nexus Mock Devices',
                'model': 'simulator',
                'manufacturer': 'home-nexus'
            }
        }
        # include state/command/topic specifics
        if 'device_class' in d:
            payload['device_class'] = d['device_class']
        if 'unit_of_measurement' in d:
            payload['unit_of_measurement'] = d['unit_of_measurement']
        if 'state_topic' in d:
            payload['state_topic'] = d['state_topic']
        if 'command_topic' in d:
            payload['command_topic'] = d['command_topic']
        client.publish(discovery_topic, json.dumps(payload), qos=1, retain=True)

    # give HA time to pick up discovery
    time.sleep(1)
    for k in STATE.keys():
        publish_state(k)


def publish_state(sensor_id):
    topic = f"{MQTT_PREFIX}/{sensor_id}/state"
    value = STATE[sensor_id]
    # normalize booleans to 'ON'/'OFF' for binary sensors/switches
    if isinstance(value, bool):
        payload = 'ON' if value else 'OFF'
    else:
        payload = str(value)
    client.publish(topic, payload, qos=1, retain=True)


def periodic_publish():
    while True:
        # simple temperature drift simulation
        STATE['temp_livingroom'] += (0.1 if STATE['switch_coffee'] else -0.02)
        publish_state('temp_livingroom')
        # motion decays to false
        if STATE['motion_livingroom']:
            STATE['motion_livingroom'] = False
            publish_state('motion_livingroom')
        time.sleep(10)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=9000)