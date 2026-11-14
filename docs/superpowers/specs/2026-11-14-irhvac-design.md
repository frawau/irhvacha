# IR HVAC (`irhvac`) — design

Date: 2026-11-14. Repo: `frawau/irhvacha`. Licence: MIT.

## Intent

Home Assistant users with an infrared-controlled air conditioner or heat pump
should be able to add it from the GUI and control everything its remote
controls: modes, setpoint (half degrees where the unit has them), fan,
both swing axes and the extra features (powerful, economy, sleep, light,
cleaning, ...).

Why a new integration:

- The SmartIR maintainers refused the pyhvac PR, and SmartIR's model (one
  learned code per mode/temperature/fan combination, YAML setup, its own
  Broadlink/ESPHome/MQTT controllers) is a poorer fit than what is now
  possible.
- Since Home Assistant 2026.4, IR emitters are entities (the `infrared`
  building block): Broadlink, ESPHome, MQTT etc. provide them, and a
  consumer integration just sends commands through the one the user picks.
  No emitter-specific code is needed.
- pyhvac 0.2.0 (pure Python, on PyPI) generates the full state for 689
  models and remotes from 121 brands, and tells exactly what each model can
  do (`device.capabilities`).

Audience: everyone, through HACS (custom repository first, then the HACS
default list). Built to Home Assistant core standards so it can move into
core later.

## Goals

- GUI-only setup (config flow + options flow); no YAML.
- One HA device per A/C unit, with a climate entity whose options come
  entirely from pyhvac's capabilities for the chosen model.
- Features that HA presets name (Boost, Eco, Sleep) are presets; the other
  features are switch / select entities on the same device.
- Optional external sensors: temperature and humidity (display only) and a
  power sensor that detects the unit being turned on/off outside HA.
- Correct output for protocols with toggle bits: the integration remembers
  what it last sent and gives it to pyhvac as `previous`.
- IR now; adding RF later must not touch the climate side.
- Documentation, including how to get an unsupported unit added to pyhvac.

## Non-goals

- SmartIR code files (uploaded or fetched). Unsupported units are handled by
  recording the remote and submitting the captures to pyhvac (see
  Documentation).
- Learning codes in the integration; receivers.
- RF emitters (door left open only).
- Domains other than climate (fans, media players, lights).
- Inferring on/off from temperature trends.
- A power detector derived from Huawei Solar consumption data (a possible
  separate project; any `binary_sensor` it produces will plug in as a power
  sensor).
- YAML configuration.

## Anti-goals (failures even if it works)

- Any model list, capability table or protocol knowledge inside the
  integration: pyhvac is the single source. A new pyhvac release that adds
  models must need no integration change.
- Emitter-specific code (Broadlink, ESPHome, ...): only the `infrared`
  building block's consumer API.
- Non-metric or local-time values in the core: setpoints are °C internally
  and to pyhvac (HA converts for °F users, see Units); timestamps are UTC.

## Constraints

- Home Assistant >= 2026.4 (the `infrared` building block). Manifest:
  `"dependencies": ["infrared"]`, `"requirements": ["pyhvac>=0.2.0,<0.3"]`.
- Core quality bar: Bronze rules of the integration quality scale (config
  flow with full test coverage, unique IDs, `has_entity_name`,
  `runtime_data`, entity event setup in `async_added_to_hass`, unique config
  entry, test before configure/setup, documentation rules).
- MIT licence; black-formatted Python.

## Approaches

- **A. HACS integration built to core standards — chosen.** Config flow
  only, translations, diagnostics, tests with
  `pytest-homeassistant-custom-component`, Bronze quality scale. Ships on our
  schedule via HACS; moving into core later is mostly copying the folder.
  Costs more up front (tests, review rules).
- **B. HACS-only, quick.** Same features, minimal tests, core rules ignored.
  Faster first release, but most of it would be redone for core, and the
  HACS default-list review checks much of the same.
- **C. Straight into core.** Rejected: months of review, and every pyhvac
  release adding models would wait for a core version bump.

## Design

### Names

Display name "IR HVAC", domain `irhvac`, repo `irhvacha`
(`custom_components/irhvac/`).

### Adding a unit (config flow)

1. Brand: searchable list from `pyhvac.registry.brands()`.
2. Model: searchable list from `registry.models(brand)`; remotes (kind
   `remote` in `pyhvac.brands.MODELS`) are marked as such.
3. Emitter: an infrared emitter entity (`infrared.async_get_emitters`).
   Abort with a clear reason when there is none.
4. Optional: temperature sensor, humidity sensor, power sensor
   (`binary_sensor`).

The entry title is "<brand> <model>"; the user can rename the device.
Sensors and the emitter can be changed later in the options flow. Several
units may share one emitter. The config entry's unique ID is
emitter + brand + model (two identical units on the same emitter would
receive the same codes anyway).

### What HA shows (one device per entry)

Device: manufacturer = brand, model = model.

**Climate entity**

- HVAC modes: pyhvac modes mapped as auto → `AUTO`, cool → `COOL`,
  heat → `HEAT`, dry → `DRY`, fan → `FAN_ONLY`, plus `OFF` (power off).
  *(Builder's call: `AUTO` rather than `HEAT_COOL`, since these units pick
  heat or cool themselves around one setpoint.)*
- Setpoint: min/max from `capabilities.temperature`; step 0.5 when its
  `decimals` include 5, else 1. Unit °C.
- Fan modes: pyhvac fan values shown by their labels (they already use
  `auto`/`low`/`medium`/`high` where those fit, which voice assistants
  expect); map back to values when sending.
- Swing: `swing_mode` from `swing_v`, `swing_horizontal_mode` from
  `swing_h`, each only if the model has it, labels as for fan.
- Presets: `none`, plus `boost` (feature `powerful`), `eco` (feature
  `economy` when it is on/off) and `sleep` (feature `sleep`), only those the
  model has. Presets are exclusive: choosing one clears the other two;
  `none` clears all three.
- Current temperature / humidity from the optional sensors.

### Units

The integration is metric like pyhvac: the climate entity declares °C, and
every setpoint it stores, restores or gives pyhvac is °C. The conversion
for users whose HA uses °F is HA's (the UI is the edge); the integration
never converts a setpoint itself and never stores a °F value.

Two places need care:

- **Incoming °F setpoints.** A °F user's whole-degree setpoint reaches the
  entity as a °C value with decimals (75 °F = 23.89 °C). The entity snaps
  it to the nearest setpoint the model allows (`TemperatureRange.snap`) and
  stores and shows the snapped value, so HA displays what was actually sent
  (e.g. 24.0 °C = 75.2 °F). How HA's frontend applies
  `target_temperature_step` for a °F user of a °C entity must be checked
  against HA's source and covered by a test with HA set to the US unit
  system. °F-native protocols (Airspool, Midea RG57-F: pyhvac's °C
  half-degree range, whole °F on the wire) must give every °F user a usable
  setpoint at each whole °F.
- **External temperature sensors** may report °F. Their value is converted
  to °C using the sensor's own `unit_of_measurement` (HA's temperature
  converter) before it becomes the entity's current temperature.

**Other entities on the same device**

- A switch for each remaining on/off feature (e.g. `light`, `cleaning`,
  `purifier`, `quiet`).
- A button for each one-shot action (`capabilities.actions`, e.g. Airspool
  `se_step`, LG `diagnostic`), sent through `encode(..., actions=...)`, so
  new actions in pyhvac need no integration change. *(Our call.)*
- A select for each feature with levels (e.g. `economy` with 80/60/40,
  `auto_bias`, `spot`). An `economy` with levels is a select, not the Eco
  preset.
- Feature names and labels are translated where we have translations,
  otherwise shown as pyhvac names them.

### State and sending

- The integration keeps the last state it sent (a pyhvac `HvacState`) and
  restores it after an HA restart (RestoreEntity). Each change builds the
  target state and calls `device.encode(previous, target)`; after a
  successful send, target becomes previous. With no previous (first use),
  `previous=None` sends the full state.
- Turning on from off restores the last on-state (mode, setpoint, fan, ...).
- While the unit is off, changing setpoint, fan, swing, a preset, a switch or
  a select sends nothing: the change is stored and goes out with the next
  power-on. *(Our call: many units beep or react to an off frame, and most
  remotes send nothing for these keys while off.)*
- Changes are sent immediately; bursts (e.g. dragging the setpoint) are
  coalesced so only the final state is sent after a short delay *(builder's
  call: around 0.5 s)*.
- A send failure (emitter unavailable, `HomeAssistantError`) is surfaced to
  the user and does not update previous.
- The climate and feature entities are unavailable while the emitter is
  (`InfraredEmitterConsumerEntity`).

### Power sensor

Any `binary_sensor`. When it turns on while the entity is off, the entity
shows the last on-state; when it turns off, the entity shows off. No codes
are sent either way: HA only catches up with what someone did with the
remote. *(Our call: always restore the last on-state instead of
SmartIR's on/off option; HA's climate entity has no plain "on" mode to show
otherwise.)*

The stored previous state's power follows the sensor: it is what the unit
is believed to be doing, not what was last sent. Several protocols (Kelon,
Daikin variants, Airwell, Panasonic, Hitachi, Electra, Whirlpool) send a
power toggle when `previous.power != target.power`; if previous kept the
last-sent power, a setpoint change after someone turned the unit on with
the remote would toggle it off, and HA's next "turn on" after a remote "off"
would send no toggle. Tests cover both directions on a toggle protocol.

### Transport (RF door)

One small internal module turns a pyhvac `Signal` into the building block's
command and sends it. The command wraps the pyhvac signal for the
`infrared-protocols` `Command` contract: carrier = `signal.carrier`, timings
from `signal.pulses` (marks and spaces in µs). The climate side only calls
this module. Adding RF later means a second kind in this module (RF
transmitters are entities too since HA 2026.5).

### Documentation (README + HA-style docs)

- What it connects to, prerequisites (HA >= 2026.4, an IR emitter entity),
  installation via HACS, setup, options, removal, entities and presets.
- Supported units: link to pyhvac's model list.
- **Getting your unit supported:** record your remote with a Broadlink and
  pyhvac's `tools/hvactest`, then open a pyhvac issue with the captures;
  once a pyhvac release adds it, an integration release follows
  automatically; update it in HACS and the unit appears in the model list.
- Power sensor examples (smart-plug threshold via a template
  binary_sensor).

### Testing and CI

- `pytest-homeassistant-custom-component`; config flow and options flow
  fully covered including aborts; a fake emitter entity records what was
  sent; tests check the timings equal pyhvac's for a few models, toggle
  protocols get the right `previous`, presets/switches/selects map to the
  right features, the power sensor updates the state without sending.
- GitHub Actions: hassfest, HACS validation, tests, black.

### Distribution

- GitHub releases; HACS custom repository, then the HACS default list.
- **New pyhvac releases reach users automatically.** HA installs a
  requirement only when the installed version does not satisfy it, so a
  range like `pyhvac>=0.2.0,<0.3` would never pull in a pyhvac release that
  adds models. Instead, a pyhvac GitHub release triggers a workflow in
  `irhvacha` (`repository_dispatch`, sent by pyhvac's release workflow with
  a token) that raises the manifest's minimum pyhvac version to the new
  release, runs the tests, and on success cuts an integration release (patch
  version bump); HACS then offers users the update. A failing test stops
  the release and leaves the bump as a PR. A pyhvac minor release (0.3) is
  not taken automatically.
- Brand icon/logo as HACS and HA require.

## Left to the builder

- Exact debounce delay, entity naming and translation keys, the icon.
- The precise `infrared-protocols` `Command` subclass details and whether
  `infrared-protocols` must also be listed in requirements.
- How the options flow handles changing the brand/model (re-add the unit
  is acceptable).
- Diagnostics content (config, capabilities summary, last sent state).
