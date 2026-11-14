# IR HVAC

<!-- ha-marketplace:exclude-start -->
[![Tests](https://github.com/frawau/irhvacha/actions/workflows/ci.yml/badge.svg)](https://github.com/frawau/irhvacha/actions/workflows/ci.yml)
[![Validate](https://github.com/frawau/irhvacha/actions/workflows/validate.yaml/badge.svg)](https://github.com/frawau/irhvacha/actions/workflows/validate.yaml)
<!-- ha-marketplace:exclude-end -->

Control infrared air conditioners and heat pumps from Home Assistant, with
everything their remote control can do: modes, setpoint (half degrees where
the unit has them), fan, both swing axes and features such as powerful,
economy, sleep, display light or self-cleaning.

IR HVAC does not replay recorded codes. It builds every command with
[pyhvac](https://github.com/frawau/pyhvac), which knows the protocols of
hundreds of models, and sends it through any infrared emitter Home
Assistant knows (Broadlink, ESPHome, MQTT, ...).

## Requirements

- Home Assistant 2026.6 or newer.
- An infrared emitter entity, provided by an integration such as Broadlink
  or ESPHome, that can reach the unit.

## Installation

On Home Assistant 2026.11 or newer, install it from the Marketplace
(Settings > Marketplace). Until it is listed there, add it with this link:

[![Open your Home Assistant instance and add this repository to the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=frawau&repository=irhvacha&category=integration)

On Home Assistant 2026.6 to 2026.10, add `https://github.com/frawau/irhvacha`
to HACS as a custom repository of type Integration.

Updates are offered in the Marketplace (or HACS) and need a restart of Home
Assistant.

## Adding a unit

Settings > Devices & services > Add integration > IR HVAC, then:

1. Pick the brand of the unit, or of its remote control.
2. Pick the model. Entries marked "(remote)" are remote controls: pick
   yours when the unit's own model is not listed.
3. Pick the infrared emitter that reaches the unit.
4. Optionally pick a room temperature sensor, a room humidity sensor and a
   power sensor (see [Power sensor](docs/power-sensor.md)).

Add the integration once per unit. Several units can share one emitter.
The emitter and the sensors can be changed later with Configure; to change
the brand or model, remove the unit and add it again.

## What you get

One device per unit, with:

- **A climate entity**: the unit's modes plus Off, its setpoint range and
  step, its fan speeds and swing positions, and the presets Boost, Eco and
  Sleep when the unit has the matching feature (they are exclusive, as
  presets are in Home Assistant).
- **A switch** for each other on/off feature (for example Quiet, Display
  light, Self-cleaning, Air purifier).
- **A select** for each feature with levels (for example Economy
  80/60/40).
- **A button** for each one-shot command the remote has.

Changes made while the unit is off are kept and sent with the next power-on.
Setpoints are in °C inside the integration; Home Assistant shows °F if you
use US units, and a setpoint snaps to the nearest one the unit supports.

## Supported units

Every brand and model [pyhvac supports](https://github.com/frawau/pyhvac#supported-models).
The names are pyhvac's. A model that works keeps working: pyhvac never drops
a model.

### Getting your unit supported

1. Record your remote with a Broadlink, using pyhvac's
   [hvactest](https://github.com/frawau/pyhvac/tree/main/tools/hvactest) tool.
2. Open an issue on [pyhvac](https://github.com/frawau/pyhvac/issues) with
   the captures, the brand, and the model of the unit and of the remote.

When a pyhvac release adds the unit, an IR HVAC release follows
automatically; update it in the Marketplace and restart.

## Removal

Remove each unit in Settings > Devices & services > IR HVAC (its stored
state is deleted with it), then remove IR HVAC in the Marketplace (or HACS)
and restart.

## Credits

- [pyhvac](https://github.com/frawau/pyhvac), which builds the commands.
- Everyone who contributed to
  [IRremoteESP8266](https://github.com/crankyoldgit/IRremoteESP8266), where
  most protocols come from.
- The [SmartIR](https://github.com/smartHomeHub/SmartIR) community, whose
  captures were the evidence for many models.

<!-- ha-marketplace:exclude-start -->
## Development

    pip install -r requirements_test.txt
    pytest
    black --check .
<!-- ha-marketplace:exclude-end -->
