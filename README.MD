# Home Nexus HA Demo

This repository contains a fully ready-to-run local Home Assistant + MQTT + mock device simulator stack you can start with `docker compose up --build`. 
It's designed to test my [Home-Nexus G-Assist](https://github.com/BenjaminBruenau/Home-Nexus) workflow plugin, so it can i.e. call the Home Assistant API or subscribe to the Home-Assistant WebSocket.

```
home-nexus-ha-demo/
├─ docker-compose.yml
├─ mosquitto/
│ └─ config/mosquitto.conf
├─ device_simulator/
│ ├─ Dockerfile
│ ├─ requirements.txt
│ ├─ main.py
│ └─ simulator_config.yaml
├─ homeassistant/
│ ├─ configuration.yaml
│ └─ packages/demo_devices.yaml
└─ README.md (this file)
```

## Prerequisites

Docker & Docker Compose

## Setup


1. Run `docker compose up --build`

2. You will now need to initialize and setup home-assistant
- open [](http://localhost:8123) and create an account

3. Configure a Long-Lived Access Token to use with Home-Nexus
- Add that token to your plugin when using the HA REST API.

4. Configure MQTT (needs to be done via the UI afaik, I do not think it is possible to do this via the configuration.yaml)
e.g. via
```
mqtt:
  broker: mosquitto
  port: 1883
  discovery: true
  discovery_prefix: homeassistant
```
- 1. Go to Settings -> Devices & services
- 2. Click Add Integration -> Search and Select **MQTT** -> **MQTT**
- 3. Set broker to the docker hostname (`mosquitto`) and port to `1883`

If you configured everything correctly you should see the Home Nexus Mock Devices in the Overview.
When you e.g. toggle the Coffee Switch this should also reflect in the device_simulator.

## Testing Locally:

- `uv sync`
- `.venv\Scripts\activate` (on windows)
- `source .venv/bin/activate` (on linux)


## How to integrate with home-nexus

### Option A — Use Home Assistant REST API
- Home Assistant exposes states at `GET /api/states/<entity_id>` and services at `POST /api/services/<domain>/<service>`.
- Example: to read living room temperature:
  - `GET http://localhost:8123/api/states/sensor.home_nexus_mock_devices_temperature_livingroom`
- To call a service (e.g., turn on a switch):
  - `POST http://localhost:8123/api/services/switch/turn_on` with JSON `{"entity_id":"switch.home_nexus_mock_devices_coffee_switch"}`
- Authentication: on first HA launch you will create a user and can generate a Long-Lived Access Token under your profile (use that in `Authorization: Bearer <token>` header).

### Option B — Use MQTT topics directly (fast, lightweight)
- Subscribe to `home/mock/+/state` to receive sensor updates.
- Publish to `home/mock/switch_coffee/set` to request switch change — the simulator listens on REST POST for changes, but you can extend it to subscribe to `set` topics and apply state changes.

### Option C — Use the simulator's REST endpoints (fast for testing)
- List sensors: `GET http://localhost:9000/sensors`
- Set sensor value: `POST http://localhost:9000/sensors/switch_coffee/set` with JSON `{"value": true}`
- Run scenario: `POST http://localhost:9000/scenarios/morning/run`


- When HA finishes initial setup, create a user and generate a Long-Lived Access Token. Add that token to your plugin when using the HA REST API.
- The provided simulator uses MQTT Discovery so Home Assistant auto-creates entities.
- You can extend `device_simulator/main.py` to subscribe to `home/mock/+/set` and apply the commands directly (making it act like a real device that reacts to commands).


## Troubleshooting

- If you don't see entities in HA: check `docker compose logs device-simulator` to ensure discovery messages were published. Check HA logs for MQTT integration messages.
- If all containers are running try restarting the device simulator `docker compose restart device-simulator` to ensure home-assistant can discover the devices

Helpful commands:
```
# watch discovery messages
docker compose exec mosquitto sh -c "mosquitto_sub -h localhost -p 1883 -t 'homeassistant/#' -v"
# watch mock states
docker compose exec mosquitto sh -c "mosquitto_sub -h localhost -p 1883 -t 'home/mock/#' -v"

docker compose logs -f device-simulator
docker compose logs -f homeassistant
```

---

Optional Add MQTT Explorer:
```
  mqtt-explorer:
    image: ccll/mqtt-explorer:latest
    restart: unless-stopped
    ports:
    - '8080:8080'
    environment:
    - MQTT_URL=ws://mosquitto:9001
    depends_on:
    - mosquitto
````

