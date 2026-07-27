# epson-projector-proxy — Design

**Status:** approved 2026-07-26 · pre-implementation
**Author:** Will Samuels (with Claude)

A small, self-hosted, MQTT-discoverable thin control wrapper for the Epson
Home Cinema 1080 projector. It speaks the projector's native **ESC/VP21
protocol over TCP 3629** and publishes **Home Assistant MQTT auto-discovery**
entities, so the projector's full controllable surface appears in HA as native
`switch` / `select` / `number` / `sensor` entities with no per-entity YAML.

It is the projector-shaped sibling of `hdmi-matrix-proxy`, reusing that
service's structure, chart, CI, and MQTT-discovery pattern.

## Why this exists

The Epson HC1080 exposes far more control over raw ESC/VP21 than either Home
Assistant integration surfaces:

- **Built-in `epson` integration** — cannot connect. It drives the projector's
  HTTP `directsend` endpoint, which on this unit is Digest-gated *and*
  command-whitelisted (`PWR?` → 200, `CONTRAST?` → 403). Dead end.
- **HACS `ha-epson-projector-link`** — works over TCP 3629 but surfaces ~7 of
  the ~20 settable parameters, with quirks we had to hand-patch (bogus lamp
  "Medium" option, `media_player` mute/volume unsupported → `send_command`
  glue, manual template `select` entities, hand-built dashboard pop-up).

A live sweep of the projector (TCP 3629, no auth) established the definitive
controllable surface:

**Settable (20):** power, source, color/picture mode, lamp power, auto-iris,
brightness, contrast, saturation, tint, sharpness, color temperature,
overscan, horizontal flip, vertical flip, digital zoom, vertical keystone,
horizontal keystone, volume, A/V mute, aspect.

**Read-only status:** lamp hours, serial number, signal-present, error state,
auto-keystone.

**Not supported on the 1080:** gamma, noise reduction, super-white,
position (HPOS/VPOS), lens/focus (no powered lens), 3D, split-screen, test
pattern, frame interpolation, progressive, and the whole `KEY` remote-emulation
family.

Owning a thin wrapper gives the complete, correct, auto-discovered surface over
a reliable no-auth transport — the same value proposition as `hdmi-matrix-proxy`.

## Non-goals (YAGNI)

- **No REST API / OpenAPI.** MQTT discovery + health probes only.
- **No HTTP `directsend` transport.** TCP 3629 is complete and needs no auth.
- **No support for models we don't own.** Registry is tuned to the HC1080;
  other Epson models are a future concern, not designed-for now.
- **No cloud / no public exposure.** Tailscale/LAN only, like every other
  service in the homelab.

## Architecture

Standalone repo `willysamz/epson-projector-proxy` (private) → ghcr image via
GitHub Actions → Fleet bundle `NN-epson-projector-proxy` (next free number,
~41) in `homelab-gitops`, chart-from-repo with values-in-bundle. Publishes to
the existing Mosquitto broker (bundle `16-mqtt`, `mqtt:1883`) using HA
discovery prefix `homeassistant`. **No new infrastructure.**

```
Home Assistant  ──MQTT discovery (homeassistant/*/config, retained)──┐
     ▲                                                                │
     │  switch/select/number/sensor.epson_projector_*                │
     │                                                                ▼
   MQTT broker (mqtt:1883)  ◄──────── epson/projector/<prop>/state (retained)
     ▲                                 epson/projector/<prop>/set    (subscribe)
     │                                 epson/projector/availability  (LWT + gate)
     │
epson-projector-proxy (this service, in your Kubernetes cluster)
     │  serialized TCP connection manager
     ▼
Epson HC1080 — ESC/VP.net, TCP 192.168.1.100:3629 (no auth)
```

### Components (one clear purpose each)

- **`config.py`** — env-driven settings (projector host/port, MQTT
  host/port/user/pass, topic prefix `epson`, discovery prefix `homeassistant`,
  poll interval, log level). Same shape as the matrix proxy's config.
- **`registry.py`** *(the heart)* — a declarative table of `Prop` rows. Each
  row: `name`, `escvp_cmd`, `entity_type`, `codec`, optional `options`,
  `category` (`primary` | `config` | `diagnostic`), and `power_gated`. This one
  table drives discovery payloads, the poll set, command routing, and value
  coding. Adding/removing a control = one row.
- **`codecs.py`** — bidirectional raw-ESC/VP21 ↔ friendly-value mappers used by
  registry rows: enum maps (`SOURCE 30↔HDMI1 / A0↔HDMI2 / 10↔PC / 20↔PC2`,
  `LUMINANCE 00↔High / 01↔ECO`, `IRIS 00/01/02↔Off/Normal/High`, `CMODE`,
  `ASPECT`, `OVSCAN`), boolean `ON/OFF↔on/off`, and pass-through numbers with
  `min`/`max`. Pure and unit-tested.
- **`esc_vp_client.py`** — a **single serialized connection manager**: one
  persistent TCP socket behind an async lock/queue (the projector is
  effectively single-session), ESC/VP.net handshake on connect, reconnect with
  backoff on error. Exposes `query(cmd)` and `set(cmd, value)`; both the poll
  loop and inbound `set` commands funnel through it so there are no
  concurrent-connection races. Replaces the matrix proxy's `matrix_client.py`.
- **`discovery.py`** — builds retained HA discovery payloads from the registry.
  One `device` block groups every entity under a single **"Epson HC1080
  Projector"** device. Per entity: `state_topic`, `command_topic` (for
  settables), `availability_topic`, and `entity_category` from the row's
  `category`.
- **`poller.py`** — background loop (default 15s). Reads `PWR?` first, then the
  gettable set. Publishes deltas to `state` topics; (re)publishes discovery on
  first cycle. Handles power-gating (below).
- **`mqtt_client.py`** — broker connection, LWT/birth on the availability
  topic, publish + subscribe. Reused near-verbatim from the matrix proxy.
- **`main.py`** — minimal app wiring + `/healthz` / `/readyz` probes. No REST
  control surface.

### The property registry & entity mapping

The registry produces this default HA surface. `category` controls clutter:
`primary` entities render on the main device card; `config` entities live in the
device's Configuration drawer; `diagnostic` are read-only sensors. **All 20
controls are always reachable — categorization only affects default placement.**

| Prop | ESC/VP21 | Entity | Category | Power-gated |
|---|---|---|---|---|
| power | `PWR` | switch | primary | no |
| source | `SOURCE` | select | primary | yes |
| picture_mode | `CMODE` | select | primary | yes |
| lamp_power | `LUMINANCE` | select (ECO/High) | primary | yes |
| auto_iris | `IRIS` | select (Off/Normal/High) | primary | yes |
| brightness | `BRIGHT` | number | primary | yes |
| mute | `MUTE` | switch | primary | yes |
| volume | `VOL?` + `VOL INC`/`DEC` | number (slider, 0–10 level) | primary | yes |
| contrast | `CONTRAST` | number | config | yes |
| saturation | `DENSITY` | number | config | yes |
| tint | `TINT` | number | config | yes |
| sharpness | `SHARP` | number | config | yes |
| color_temp | `CTEMP` | number | config | yes |
| overscan | `OVSCAN` | select | config | yes |
| h_flip | `HREVERSE` | switch | config | yes |
| v_flip | `VREVERSE` | switch | config | yes |
| zoom | `ZOOM` | number | config | yes |
| v_keystone | `VKEYSTONE` | number | config | yes |
| h_keystone | `HKEYSTONE` | number | config | yes |
| aspect | `ASPECT` | select | config | yes |
| lamp_hours | `LAMP` | sensor | diagnostic | no |
| signal | `SIGNAL` | sensor | diagnostic | no |
| serial | `SNO` | sensor | diagnostic | no |

**Known unknown, retired in Phase 1:** the exact `CMODE` and `ASPECT`
code↔name maps for the 1080 are not fully pinned. Each code is verified live
against the projector during the build and the confirmed map is baked into the
registry. **Volume** is exposed as a slider despite relative-only hardware: `VOL?`
returns an absolute 0–255 value moving in ~11 discrete ~23-wide steps, so the
proxy maps raw↔level (0–10) for display and, on a set, issues the delta number
of `VOL INC`/`VOL DEC` commands to reach the target level. Absolute set
(`VOL <n>`) is **not** used — it proved unreliable during verification
(returned an ambiguous ack and reset to 0). Two `INC`/`DEC` buttons remain the
fallback if the readback-driven slider proves flaky. `MUTE` uses `MUTE ON/OFF`.
Number ranges (`BRIGHT` etc.) are confirmed live and encoded as each row's
`min`/`max`.

### I/O model & power-gating

All projector I/O is serialized through the one connection manager, so the poll
loop and command handling never open competing sockets. The projector keeps its
LAN alive in standby ("Communication On" is enabled — proven by the fact that
Projector Link wakes it today over the same port), so:

- **Power on/off always works.** The `power` switch is **not** power-gated; it
  sits on the base availability topic and issues the same `PWR ON`/`PWR OFF`
  over TCP 3629 that works today. `PWR?` is readable in standby (returns off),
  so HA always shows true state. This is a strict reliability upgrade over the
  HACS integration, not a change to the wake path.
- **Two availability topics.** `epson/projector/availability` (proxy ↔
  projector reachable) backs `power` and the diagnostic sensors.
  `epson/projector/power_avail` (reachable **and** powered on) backs every
  picture/geometry entity, so those correctly grey-out in HA when the projector
  is off — matching the projector's own behaviour of returning `ERR` for those
  reads/writes in standby.

Command flow: MQTT `set` → codec-encode → enqueue on the connection manager →
optimistic `state` publish → reconciled on the next poll read.

## Home Assistant migration (replace Projector Link)

Once the discovery entities appear and are verified live, migrate the HA side:

1. Repoint the Garage tab pop-up and the Summary "Media" pop-up at the new
   `switch./select./number./sensor.epson_projector_*` entities.
2. Delete the projector template `select` entities and the `send_command`
   glue from `configuration.yaml`.
3. Uninstall the `ha-epson-projector-link` HACS integration and remove its
   config entry.

Result: one owned control path; no third-party integration, no template glue,
no hand-built command actions.

## Configuration (chart values)

`projector.host` / `projector.port`, `mqtt.host` / `port` / `username` /
`password`, `topicPrefix` (`epson`), `discoveryPrefix` (`homeassistant`),
`pollIntervalSeconds` (default **15**, operator-tunable from the Fleet
bundle's Helm values → env → poller), `logLevel`. MQTT credentials, if the
broker requires them, come from the cluster the same way the matrix proxy's do.

## Testing

- **Codec round-trips** — every enum/boolean/number map, both directions,
  including unknown-code handling.
- **Registry → discovery payload builder** — asserts topic structure,
  `device` grouping, `entity_category`, and availability-topic selection per
  row.
- **Fake-projector TCP stub** — a small asyncio server that speaks the
  ESC/VP.net handshake and canned command responses, to exercise the
  connection manager, command round-trips, reconnect, and power-gating.
  (Mirrors the matrix proxy's `tests/` approach.)

## Documentation (repo conventions)

In `homelab-gitops` / the docs site: app card
`docs/content/architecture/apps/NN-epson-projector-proxy.md`, a `doc-sync.yaml`
mapping, and an `mkdocs.yml` nav entry; a project page; and updates to the
existing projector/HA notes to reflect the migration off Projector Link.
`mkdocs build --strict` gates the bundle commit.

## Phased build (value early, risk first)

1. **Client + registry + codecs** — pure, unit-tested, verified against the
   live projector. Retires the `CMODE`/`ASPECT`/number-range unknowns.
2. **MQTT discovery + poller + command routing** — entities appear in HA;
   power-gating works end-to-end.
3. **Chart + Fleet bundle + CI/ghcr** — image builds and deploys in-cluster.
4. **HA migration** — remove Projector Link + template glue; rebuild dashboards
   on MQTT entities.
5. **Docs + strict build.**

## Security notes

- No inbound public exposure — Tailscale/LAN only, consistent with the repo.
- Projector transport needs no credentials. If the MQTT broker requires auth,
  credentials are injected from the cluster, never committed.
- The projector's HTTP Web Control password is unrelated to this service and
  is not used.
