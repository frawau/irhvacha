"""Config flow (the integration, once) and the unit subentry flow."""

from homeassistant import config_entries
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irhvac.const import DOMAIN, SUBENTRY_UNIT

from .conftest import FakeEmitter, add_unit


async def _entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="IR HVAC", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _start_unit(hass, entry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_UNIT),
        context={"source": config_entries.SOURCE_USER},
    )


async def _to_device_step(hass, entry, brand):
    result = await _start_unit(hass, entry)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"brand": brand}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "device"
    return result


def _selector_config(result, field):
    for key, selector in result["data_schema"].schema.items():
        if key == field:
            return selector.config
    raise AssertionError(f"no field {field}")


async def test_adding_the_integration_asks_nothing(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IR HVAC"
    assert result["data"] == {}


async def test_second_entry_aborts(hass):  # Review Focus 4
    await _entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_unit_flow_creates_subentry(hass, emitter):
    entry = await _entry(hass)
    result = await _to_device_step(hass, entry, "AEG")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"model": "Chillflex Pro AXP26U558HW", "emitter": emitter.entity_id},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    (subentry,) = entry.subentries.values()
    assert subentry.title == "AEG Chillflex Pro AXP26U558HW"
    assert dict(subentry.data) == {
        "brand": "AEG",
        "model": "Chillflex Pro AXP26U558HW",
        "emitter": emitter.entity_id,
    }
    assert subentry.unique_id == f"{emitter.entity_id}|AEG|Chillflex Pro AXP26U558HW"
    assert entry.runtime_data[subentry.subentry_id].model == (
        "Chillflex Pro AXP26U558HW"
    )


async def test_unit_flow_no_emitters_aborts(hass):
    assert await async_setup_component(hass, "infrared", {})
    entry = await _entry(hass)
    result = await _start_unit(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_emitters"


async def test_unit_flow_duplicate_aborts(hass, emitter):
    added = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    result = await _to_device_step(hass, added.entry, "AEG")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"model": "Chillflex Pro AXP26U558HW", "emitter": emitter.entity_id},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_remote_models_are_labelled(hass, emitter):
    entry = await _entry(hass)
    result = await _to_device_step(hass, entry, "Mitsubishi Electric")
    models = _selector_config(result, "model")["options"]
    assert {"value": "PAR-FL32MA", "label": "PAR-FL32MA (remote)"} in models
    assert {"value": "MSZ-GV2519", "label": "MSZ-GV2519"} in models


async def test_optional_sensors_stored(hass, emitter):
    entry = await _entry(hass)
    result = await _to_device_step(hass, entry, "AEG")
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "model": "Chillflex Pro AXP26U338CW",
            "emitter": emitter.entity_id,
            "temperature_sensor": "sensor.room_temperature",
            "humidity_sensor": "sensor.room_humidity",
            "power_sensor": "binary_sensor.ac_power",
        },
    )
    (subentry,) = entry.subentries.values()
    assert dict(subentry.data) == {
        "brand": "AEG",
        "model": "Chillflex Pro AXP26U338CW",
        "emitter": emitter.entity_id,
        "temperature_sensor": "sensor.room_temperature",
        "humidity_sensor": "sensor.room_humidity",
        "power_sensor": "binary_sensor.ac_power",
    }


async def _other_emitter(hass):
    other = FakeEmitter("Other emitter")
    await hass.data[DATA_COMPONENT].async_add_entities([other])
    await hass.async_block_till_done()
    return other


async def _reconfigure(hass, added, user_input):
    result = await added.entry.start_subentry_reconfigure_flow(hass, added.id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()
    return result


async def test_reconfigure_updates_and_reloads(hass, emitter):
    other = await _other_emitter(hass)
    added = await add_unit(
        hass,
        emitter,
        "AEG",
        "Chillflex Pro AXP26U338CW",
        temperature_sensor="sensor.room_temperature",
    )
    result = await _reconfigure(
        hass,
        added,
        {"emitter": other.entity_id, "power_sensor": "binary_sensor.ac_power"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = added.entry.subentries[added.id]
    assert dict(subentry.data) == {
        "brand": "AEG",
        "model": "Chillflex Pro AXP26U338CW",
        "emitter": other.entity_id,
        "power_sensor": "binary_sensor.ac_power",
    }
    assert subentry.unique_id == f"{other.entity_id}|AEG|Chillflex Pro AXP26U338CW"
    assert added.unit.emitter == other.entity_id


async def test_reconfigure_to_existing_unit_aborts(hass, emitter):  # RF 2
    other = await _other_emitter(hass)
    await add_unit(hass, other, "AEG", "Chillflex Pro AXP26U338CW")
    added = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    result = await _reconfigure(hass, added, {"emitter": other.entity_id})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert added.entry.subentries[added.id].data["emitter"] == emitter.entity_id
