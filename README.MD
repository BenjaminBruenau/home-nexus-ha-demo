

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

docker compose up --build


you will first need to open  http://localhost:8123 and create an account


only if you want to test :

uv sync


.venv\Scripts\activate (on windows)

source .venv/bin/activate (on linux)

How to integrate with home-nexus
Option A — Use Home Assistant REST API (realistic)

Home Assistant exposes states at GET /api/states/<entity_id> and services at POST /api/services/<domain>/<service>.

Example: to read living room temperature:

GET http://localhost:8123/api/states/sensor.temp_livingroom

To call a service (e.g., turn on a switch):

POST http://localhost:8123/api/services/switch/turn_on with JSON {"entity_id":"switch.coffee"}

Authentication: on first HA launch you will create a user and can


## How to integrate with home-nexus

### Option A — Use Home Assistant REST API (realistic)
- Home Assistant exposes states at `GET /api/states/<entity_id>` and services at `POST /api/services/<domain>/<service>`.
- Example: to read living room temperature:
  - `GET http://localhost:8123/api/states/sensor.temp_livingroom`
- To call a service (e.g., turn on a switch):
  - `POST http://localhost:8123/api/services/switch/turn_on` with JSON `{"entity_id":"switch.coffee"}`
- Authentication: on first HA launch you will create a user and can generate a Long-Lived Access Token under your profile (use that in `Authorization: Bearer <token>` header).

### Option B — Use MQTT topics directly (fast, lightweight)
- Subscribe to `home/mock/+/state` to receive sensor updates.
- Publish to `home/mock/switch_coffee/set` to request switch change — the simulator listens on REST POST for changes, but you can extend it to subscribe to `set` topics and apply state changes.

### Option C — Use the simulator's REST endpoints (fast for testing)
- List sensors: `GET http://localhost:9000/sensors`
- Set sensor value: `POST http://localhost:9000/sensors/switch_coffee/set` with JSON `{"value": true}`
- Run scenario: `POST http://localhost:9000/scenarios/morning/run`


- When HA finishes initial setup, create a user and generate a Long-Lived Access Token. Add that token to your plugin when using the HA REST API.
- The provided simulator uses MQTT Discovery so Home Assistant auto-creates entities. If you later swap in real devices that also publish discovery payloads, HA will seamlessly adopt them.
- You can extend `device_simulator/main.py` to subscribe to `home/mock/+/set` and apply the commands directly (making it act like a real device that reacts to commands).


## Troubleshooting

- If you don't see entities in HA: check `docker compose logs device-simulator` to ensure discovery messages were published. Check HA logs for MQTT integration messages.
- If MQTT Explorer can't connect: ensure websockets on port 9001 are exposed and mosquitto has websockets enabled (see mosquitto.conf).


---


  mqtt-explorer:
    image: ccll/mqtt-explorer:latest
    restart: unless-stopped
    ports:
    - '8080:8080'
    environment:
    - MQTT_URL=ws://mosquitto:9001
    depends_on:
    - mosquitto