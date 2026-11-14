"""Config flow and options flow."""

from homeassistant import config_entries
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.irhvac.const import DOMAIN

from .conftest import FakeEmitter, add_unit


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _to_device_step(hass, brand):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"brand": brand}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "device"
    return result


def _selector_config(result, field):
    for key, selector in result["data_schema"].schema.items():
        if key == field:
            return selector.config
    raise AssertionError(f"no field {field}")


async def test_flow_creates_entry(hass, emitter):
    result = await _to_device_step(hass, "AEG")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"model": "Chillflex Pro AXP26U558HW", "emitter": emitter.entity_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AEG Chillflex Pro AXP26U558HW"
    assert result["data"] == {"brand": "AEG", "model": "Chillflex Pro AXP26U558HW"}
    assert result["options"] == {"emitter": emitter.entity_id}
    entry = result["result"]
    assert entry.unique_id == f"{emitter.entity_id}|AEG|Chillflex Pro AXP26U558HW"


async def test_no_emitters_aborts(hass):
    assert await async_setup_component(hass, "infrared", {})
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


async def test_duplicate_aborts(hass, emitter):
    await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    result = await _to_device_step(hass, "AEG")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"model": "Chillflex Pro AXP26U558HW", "emitter": emitter.entity_id},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_remote_models_are_labelled(hass, emitter):
    result = await _to_device_step(hass, "Mitsubishi Electric")
    models = _selector_config(result, "model")["options"]
    assert {"value": "PAR-FL32MA", "label": "PAR-FL32MA (remote)"} in models
    assert {"value": "MSZ-GV2519", "label": "MSZ-GV2519"} in models


async def test_optional_sensors_stored(hass, emitter):
    result = await _to_device_step(hass, "AEG")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "model": "Chillflex Pro AXP26U338CW",
            "emitter": emitter.entity_id,
            "temperature_sensor": "sensor.room_temperature",
            "humidity_sensor": "sensor.room_humidity",
            "power_sensor": "binary_sensor.ac_power",
        },
    )
    assert result["options"] == {
        "emitter": emitter.entity_id,
        "temperature_sensor": "sensor.room_temperature",
        "humidity_sensor": "sensor.room_humidity",
        "power_sensor": "binary_sensor.ac_power",
    }


async def test_options_flow_updates_and_reloads(hass, emitter):
    other = FakeEmitter("Other emitter")
    await hass.data[DATA_COMPONENT].async_add_entities([other])
    await hass.async_block_till_done()
    entry = await add_unit(
        hass,
        emitter,
        "AEG",
        "Chillflex Pro AXP26U338CW",
        temperature_sensor="sensor.room_temperature",
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"emitter": other.entity_id, "power_sensor": "binary_sensor.ac_power"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {
        "emitter": other.entity_id,
        "power_sensor": "binary_sensor.ac_power",
    }
    assert entry.runtime_data.emitter == other.entity_id
