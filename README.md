# epson-projector-proxy

A small, self-hosted control wrapper for Epson projectors that speaks the
projector's native **ESC/VP21 protocol over TCP (port 3629)** and publishes
**Home Assistant MQTT auto-discovery** entities — so the projector's full
controllable surface shows up in Home Assistant as native `switch` / `select`
/ `number` / `sensor` entities with no per-entity YAML.

It is the projector-shaped sibling of a similar HDMI-matrix MQTT wrapper:
a thin, discoverable shim over a device whose stock integrations are awkward
or incomplete.

## What it controls

Driven by a single declarative property registry, the proxy exposes (on a
tested Epson Home Cinema 1080):

- **Primary:** power, source, picture/color mode, lamp power (ECO/High),
  auto-iris, brightness, A/V mute, volume (a real slider, backed by
  absolute-read + relative INC/DEC stepping).
- **Configuration:** contrast, saturation, tint, sharpness, color temperature,
  horizontal/vertical flip, digital zoom, horizontal/vertical keystone
  (surfaced in Home Assistant's device *Configuration* section).
- **Diagnostics:** lamp hours, signal status, serial number.

Power-gating: picture/geometry entities grey out in Home Assistant while the
projector is off; power and source stay live so you can turn it on.

## How it works

```
Home Assistant ──MQTT discovery (retained)──┐
     ▲  switch/select/number/sensor.*        │
     │                                        ▼
   MQTT broker  ◄── epson/<prop>/state (retained) · epson/<prop>/set · availability
     ▲
epson-projector-proxy  ──serialized TCP──►  Epson projector (ESC/VP.net :3629, no auth)
```

A background poller reads the projector on an interval and publishes state
deltas; commands arriving on `epson/<prop>/set` are translated to ESC/VP21 and
applied. All projector I/O is serialized through a single connection that
reconnects on error.

## Quick start

### Docker

```bash
docker run -d \
  --name epson-projector-proxy \
  -e PROJECTOR_HOST=192.168.1.100 \
  -e MQTT_HOST=your-broker \
  ghcr.io/willysamz/epson-projector-proxy:latest
```

### Helm

```bash
helm install epson ./chart \
  --set config.projectorHost=192.168.1.100 \
  --set mqtt.host=your-broker
```

## Configuration

Environment variables (all optional; shown with defaults):

| Variable | Default | Description |
|---|---|---|
| `PROJECTOR_HOST` | `192.168.1.100` | Projector IP/hostname |
| `PROJECTOR_PORT` | `3629` | ESC/VP.net TCP port |
| `POLL_INTERVAL` | `15.0` | Seconds between state polls |
| `MQTT_HOST` | `mqtt` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC_PREFIX` | `epson` | Topic prefix for state/command/availability |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant MQTT discovery prefix |
| `HA_DEVICE_NAME` | `Epson Projector` | Device name shown in Home Assistant |
| `HA_DEVICE_ID` | `epson_projector` | Stable device/entity id prefix |

The Helm chart exposes the same settings under `config.*`, `mqtt.*`, and `ha.*`
(see `chart/values.yaml`).

## Health

- `GET /healthz/live` — liveness
- `GET /healthz/ready` — readiness (reports projector connectivity)

## Development

```bash
make install   # create venv + install deps
make test      # run the test suite
make lint      # ruff + mypy
make helm-lint # lint the chart
```

See [`docs/DESIGN.md`](docs/DESIGN.md) for the architecture and the rationale
behind the controllable surface.

## License

See [`LICENSE`](LICENSE).
