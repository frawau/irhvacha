# IR HVAC units as subentries — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The integration is added once; A/C units are config subentries of it.

**Architecture:** One config entry (`single_config_entry`), `runtime_data` =
`dict[subentry_id, IrHvacUnit]`. Platforms add each unit's entities with
`config_subentry_id`. A `ConfigSubentryFlow` (type `unit`) adds and
reconfigures units. An update listener removes stores of deleted units and
reloads.

**Tech Stack:** HA ≥ 2026.6 config subentries, pyhvac 0.2.0.

**Spec:** docs/superpowers/specs/2026-11-14-irhvac-design.md, section
"The integration and its units".

## Global Constraints

- Everything from the original plan's Global Constraints still holds (HA ≥ 2026.6, `pyhvac==0.2.0`, translations/en.json only, °C core, black).
- No migration: 0.1.0 was never released.
- Subentry type key: `unit`. Store key: `irhvac.<subentry_id>`.
- Unique ids: climate `<subentry_id>`, switch/select `<subentry_id>_<feature>`, button `<subentry_id>_action_<name>`; device identifier `(irhvac, <subentry_id>)`.
- Subentry unique id: `<emitter>|<brand>|<model>`.

## Review Focus

1. Deleting one unit: its entities, device and store go; other units keep state.
2. Reconfigure to an emitter|brand|model another unit already has: refused (`already_configured`), nothing changes.
3. A unit with an unknown model among good ones: skipped with an error log, others load.
4. Second "Add integration": aborted (single instance).
5. Adding a unit while another unit's send is pending/powered: reload restores state and previous from the store.

---

### Task 1: Entry with unit subentries (setup, platforms, entities, test helpers)

**Files:** `__init__.py`, `entity.py`, `climate.py`, `switch.py`, `select.py`, `button.py`, `manifest.json`, `tests/conftest.py`, `tests/test_climate.py`, `tests/test_entities.py`, `tests/test_unit.py`, new `tests/test_init.py`.

**Interfaces:**
- Produces: `IrHvacConfigEntry = ConfigEntry[dict[str, IrHvacUnit]]`; `SUBENTRY_UNIT = "unit"` in const; entity constructors take `(entry, subentry_id, unit)`.
- Test helper `add_unit(hass, emitter, brand=..., model=..., **options) -> Added` where `Added` has `entry`, `id` (subentry id) and `unit`; it reuses the one IR HVAC entry.

- [ ] Rewrite helper and existing tests to `Added` (`added.id` for unique ids, `added.unit` for the unit); run → RED (import/setup errors).
- [ ] New tests in `tests/test_init.py`: `test_two_units_one_entry` (two devices, both climates), `test_deleting_a_unit_removes_its_store_and_entities` (other unit keeps its stored state), `test_unknown_model_is_skipped` (bad subentry logs error; good one loads).
- [ ] Implement; manifest `"single_config_entry": true`.
- [ ] Full suite green; black; commit.

### Task 2: Config flow and unit subentry flow

**Files:** `config_flow.py`, `translations/en.json`, `tests/test_config_flow.py`.

- [ ] Tests: `test_adding_the_integration_asks_nothing`, `test_second_entry_aborts`, `test_unit_flow_creates_subentry` (title, data, unique id), `test_unit_flow_no_emitters_aborts`, `test_unit_flow_duplicate_aborts`, `test_remote_models_are_labelled`, `test_optional_sensors_stored`, `test_reconfigure_updates_and_reloads`, `test_reconfigure_to_existing_unit_aborts`.
- [ ] Implement: `IrHvacConfigFlow.async_step_user` creates entry "IR HVAC" with empty data; `async_get_supported_subentry_types` → `{"unit": UnitSubentryFlow}`; `UnitSubentryFlow` steps `user` (brand), `device`, `reconfigure`. Options flow removed. Translations under `config_subentries.unit` (`entry_type` "A/C unit", `initiate_flow.user` "Add A/C unit").
- [ ] Suite green; commit.

### Task 3: Diagnostics

**Files:** `diagnostics.py`, `tests/test_diagnostics.py`.

- [ ] Tests: entry diagnostics hold `pyhvac` and `units` keyed by subentry id (title, data, capabilities, state, previous); device diagnostics give the one unit.
- [ ] Implement `async_get_config_entry_diagnostics` and `async_get_device_diagnostics`.
- [ ] Suite green; commit.

### Task 4: Docs

**Files:** `README.md`, `docs/power-sensor.md`, `quality_scale.yaml` (check only).

- [ ] README "Adding a unit": add the integration once, then "Add A/C unit" per unit; Reconfigure on a unit; removal of a unit vs the integration.
- [ ] power-sensor.md: "Reconfigure on the unit".
- [ ] Commit. Then final review.
