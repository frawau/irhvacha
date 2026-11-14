"""One IR HVAC entry holding the A/C units as subentries."""

import asyncio
import logging

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irhvac.const import DOMAIN, STORAGE_VERSION

from .conftest import add_unit, unit_subentry


def climate_id(hass, unit_id):
    return er.async_get(hass).async_get_entity_id("climate", DOMAIN, unit_id)


async def test_two_units_one_entry(hass, emitter):
    first = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    second = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    assert first.entry is second.entry
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    devices = dr.async_entries_for_config_entry(
        dr.async_get(hass), first.entry.entry_id
    )
    assert {d.model for d in devices} == {"FTXM20R5V1B", "Chillflex Pro AXP26U558HW"}
    for added in (first, second):
        assert hass.states.get(climate_id(hass, added.id)).state == HVACMode.OFF
        entity = er.async_get(hass).async_get(climate_id(hass, added.id))
        assert entity.config_subentry_id == added.id


async def test_adding_a_unit_keeps_the_others_state(hass, emitter):  # RF 5
    first = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": climate_id(hass, first.id), "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    previous = first.unit.previous
    await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    assert hass.states.get(climate_id(hass, first.id)).state == HVACMode.HEAT
    assert first.unit.previous == previous


async def test_deleting_a_unit_removes_it_and_its_store(hass, emitter):  # RF 1
    gone = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    kept = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": climate_id(hass, gone.id), "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": climate_id(hass, kept.id), "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    assert await Store(hass, STORAGE_VERSION, f"irhvac.{gone.id}").async_load()
    hass.config_entries.async_remove_subentry(gone.entry, gone.id)
    await hass.async_block_till_done()
    assert climate_id(hass, gone.id) is None
    assert (
        dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, gone.id), gone.entry.entry_id
        )
        is None
    )
    assert await Store(hass, STORAGE_VERSION, f"irhvac.{gone.id}").async_load() is None
    assert hass.states.get(climate_id(hass, kept.id)).state == HVACMode.HEAT


async def test_unknown_model_is_skipped(hass, emitter, caplog):  # RF 3
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="IR HVAC",
        data={},
        subentries_data=[
            unit_subentry("Daikin", "Gone 9000", emitter=emitter.entity_id),
            unit_subentry(
                "AEG", "Chillflex Pro AXP26U558HW", emitter=emitter.entity_id
            ),
        ],
    )
    entry.add_to_hass(hass)
    with caplog.at_level(logging.ERROR):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert "Gone 9000" in caplog.text
    assert [u.model for u in entry.runtime_data.values()] == [
        "Chillflex Pro AXP26U558HW"
    ]


async def test_removing_the_integration_removes_all_stores(hass, emitter):
    added = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": climate_id(hass, added.id), "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await hass.config_entries.async_remove(added.entry.entry_id)
    await hass.async_block_till_done()
    assert await Store(hass, STORAGE_VERSION, f"irhvac.{added.id}").async_load() is None


async def test_reload_during_a_send_keeps_what_was_sent(hass, emitter):  # RF 5
    first = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    emitter.delay = 0.2
    send = hass.async_create_task(
        hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_id(hass, first.id), "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )
    )
    await asyncio.sleep(0.05)
    await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    await send
    await hass.async_block_till_done()
    assert len(emitter.sent) == 1
    unit = first.unit
    assert unit.state.power is True and unit.state.mode == "heat"
    assert unit.previous == unit.state
    assert hass.states.get(climate_id(hass, first.id)).state == HVACMode.HEAT


async def test_closed_unit_sends_nothing(hass, emitter):
    from custom_components.irhvac.unit import IrHvacUnit

    unit = IrHvacUnit(hass, "u9", "Daikin", "FTXM20R5V1B", emitter.entity_id)
    await unit.async_load()
    await unit.async_shutdown()
    with pytest.raises(HomeAssistantError):
        await unit.async_set(power=True)
    assert emitter.sent == []
