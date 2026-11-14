"""The climate entity, its sensors and the power sensor."""

from dataclasses import replace

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pyhvac.ir.formats import to_raw
from pyhvac.state import HvacState

from custom_components.irhvac.mapping import options, preset_modes

from .conftest import add_unit


def climate_id(hass, entry):
    return er.async_get(hass).async_get_entity_id("climate", "irhvac", entry.entry_id)


async def call(hass, service, entity_id, **data):
    await hass.services.async_call(
        "climate", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_capabilities_drive_the_entity(hass, emitter):
    entry = await add_unit(hass, emitter, "Mitsubishi Electric", "MSZ-GV2519")
    caps = entry.runtime_data.capabilities
    attrs = hass.states.get(climate_id(hass, entry)).attributes
    assert attrs["hvac_modes"][0] == HVACMode.OFF and len(attrs["hvac_modes"]) == 6
    assert (attrs["min_temp"], attrs["max_temp"], attrs["target_temp_step"]) == (
        16,
        31,
        0.5,
    )
    assert attrs["fan_modes"] == options(caps.fan)
    assert attrs["swing_modes"] == options(caps.swing_v)
    assert attrs["swing_horizontal_modes"] == options(caps.swing_h)
    assert attrs["preset_modes"] == preset_modes(caps)
    features = ClimateEntityFeature(attrs["supported_features"])
    for flag in (
        ClimateEntityFeature.TARGET_TEMPERATURE,
        ClimateEntityFeature.TURN_ON,
        ClimateEntityFeature.TURN_OFF,
        ClimateEntityFeature.FAN_MODE,
        ClimateEntityFeature.SWING_MODE,
        ClimateEntityFeature.SWING_HORIZONTAL_MODE,
        ClimateEntityFeature.PRESET_MODE,
    ):
        assert flag in features


async def test_whole_degree_model_without_presets(hass, emitter):
    entry = await add_unit(hass, emitter, "Airwell", "DC Series")
    attrs = hass.states.get(climate_id(hass, entry)).attributes
    assert attrs["target_temp_step"] == 1.0
    assert "preset_modes" not in attrs
    assert ClimateEntityFeature.PRESET_MODE not in ClimateEntityFeature(
        attrs["supported_features"]
    )


async def test_set_temperature_sends_pyhvac_timings(hass, emitter):
    entry = await add_unit(hass, emitter)
    unit = entry.runtime_data
    eid = climate_id(hass, entry)
    await call(hass, "set_temperature", eid, temperature=23.5, hvac_mode=HVACMode.COOL)
    expected = unit.device.encode(
        None, unit.device.normalise(replace(unit.state, temperature=23.5))
    )
    assert len(emitter.sent) == 1
    assert emitter.sent[0] == (expected.signal.carrier, to_raw(expected.signal))
    state = hass.states.get(eid)
    assert state.state == HVACMode.COOL and state.attributes["temperature"] == 23.5


async def test_fahrenheit_user_gets_snapped_setpoint(hass, emitter):
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = await add_unit(hass, emitter)
    eid = climate_id(hass, entry)
    await call(hass, "set_temperature", eid, temperature=75, hvac_mode=HVACMode.COOL)
    assert entry.runtime_data.state.temperature == 24.0
    assert hass.states.get(eid).attributes["temperature"] == 75


async def test_off_and_on_restore_last_settings(hass, emitter):
    entry = await add_unit(hass, emitter)
    eid = climate_id(hass, entry)
    await call(hass, "set_hvac_mode", eid, hvac_mode=HVACMode.HEAT)
    await call(
        hass,
        "set_fan_mode",
        eid,
        fan_mode=options(entry.runtime_data.capabilities.fan)[-1],
    )
    await call(hass, "turn_off", eid)
    assert hass.states.get(eid).state == HVACMode.OFF
    await call(hass, "turn_on", eid)
    state = hass.states.get(eid)
    assert state.state == HVACMode.HEAT
    assert (
        state.attributes["fan_mode"] == options(entry.runtime_data.capabilities.fan)[-1]
    )


async def test_preset_boost_sets_powerful(hass, emitter):
    entry = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    eid = climate_id(hass, entry)
    await call(hass, "set_hvac_mode", eid, hvac_mode=HVACMode.COOL)
    await call(hass, "set_preset_mode", eid, preset_mode="eco")
    await call(hass, "set_preset_mode", eid, preset_mode="boost")
    features = entry.runtime_data.state.features
    assert features["powerful"] is True and features["economy"] is False
    assert hass.states.get(eid).attributes["preset_mode"] == "boost"


async def test_swing_modes(hass, emitter):
    entry = await add_unit(hass, emitter)
    caps = entry.runtime_data.capabilities
    eid = climate_id(hass, entry)
    await call(hass, "set_hvac_mode", eid, hvac_mode=HVACMode.COOL)
    await call(hass, "set_swing_mode", eid, swing_mode=options(caps.swing_v)[-1])
    await call(
        hass,
        "set_swing_horizontal_mode",
        eid,
        swing_horizontal_mode=options(caps.swing_h)[-1],
    )
    state = entry.runtime_data.state
    assert state.swing_v == caps.swing_v.values[-1]
    assert state.swing_h == caps.swing_h.values[-1]


async def test_emitter_unavailable_makes_entity_unavailable(hass, emitter):
    entry = await add_unit(hass, emitter)
    eid = climate_id(hass, entry)
    hass.states.async_set(emitter.entity_id, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == "unavailable"


async def test_temperature_sensor_in_fahrenheit(hass, emitter):
    hass.states.async_set("sensor.room", "77", {"unit_of_measurement": "°F"})
    entry = await add_unit(hass, emitter, temperature_sensor="sensor.room")
    eid = climate_id(hass, entry)
    assert hass.states.get(eid).attributes["current_temperature"] == 25.0
    hass.states.async_set("sensor.room", "68", {"unit_of_measurement": "°F"})
    await hass.async_block_till_done()
    assert hass.states.get(eid).attributes["current_temperature"] == 20.0


async def test_humidity_sensor(hass, emitter):
    hass.states.async_set("sensor.hum", "55.5", {"unit_of_measurement": "%"})
    entry = await add_unit(hass, emitter, humidity_sensor="sensor.hum")
    assert (
        hass.states.get(climate_id(hass, entry)).attributes["current_humidity"] == 55.5
    )


@pytest.mark.parametrize("bad", ["unknown", "unavailable", "abc"])
async def test_bad_sensor_values(hass, emitter, bad):  # Review Focus 4
    hass.states.async_set("sensor.room", "21", {"unit_of_measurement": "°C"})
    entry = await add_unit(hass, emitter, temperature_sensor="sensor.room")
    eid = climate_id(hass, entry)
    hass.states.async_set("sensor.room", bad, {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert hass.states.get(eid).attributes["current_temperature"] is None


async def test_power_sensor(hass, emitter):  # Review Focus 5
    hass.states.async_set("binary_sensor.ac", "off")
    entry = await add_unit(hass, emitter, power_sensor="binary_sensor.ac")
    eid = climate_id(hass, entry)
    await call(hass, "set_hvac_mode", eid, hvac_mode=HVACMode.HEAT)
    await call(hass, "turn_off", eid)
    sent = len(emitter.sent)
    hass.states.async_set("binary_sensor.ac", "on")
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == HVACMode.HEAT
    hass.states.async_set("binary_sensor.ac", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == HVACMode.HEAT
    hass.states.async_set("binary_sensor.ac", "off")
    await hass.async_block_till_done()
    assert hass.states.get(eid).state == HVACMode.OFF
    assert len(emitter.sent) == sent


async def test_send_failure_raises_to_caller(hass, emitter):
    entry = await add_unit(hass, emitter)
    eid = climate_id(hass, entry)
    emitter.fail = True
    with pytest.raises(HomeAssistantError):
        await call(hass, "set_hvac_mode", eid, hvac_mode=HVACMode.COOL)
    assert hass.states.get(eid).state == HVACMode.OFF
