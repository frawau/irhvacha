"""The unit: desired and previous state, persistence, serialised sending."""

import asyncio
from dataclasses import replace

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from pyhvac.ir.formats import to_raw
from pyhvac.state import HvacState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irhvac.const import DOMAIN

from .conftest import make_unit


async def test_first_send_is_full_state_then_previous_is_used(hass, emitter):
    unit = await make_unit(hass, emitter, "Mitsubishi Electric", "MSZ-GV2519")
    await unit.async_set(power=True, mode="cool", temperature=23.5)
    dev = unit.device
    first = dev.encode(None, dev.normalise(HvacState(True, "cool", 23.5)))
    assert emitter.sent[-1][1] == to_raw(first.signal)
    assert unit.previous == first.state and unit.state == first.state
    await unit.async_set(temperature=25.0)
    second = dev.encode(first.state, replace(first.state, temperature=25.0))
    assert emitter.sent[-1][1] == to_raw(second.signal)


async def test_changes_while_off_are_stored_not_sent(hass, emitter):
    unit = await make_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    await unit.async_set(temperature=26.0, features={"light": True})
    assert emitter.sent == []
    assert unit.state.temperature == 26.0 and unit.state.power is False
    assert unit.state.features["light"] is True
    await unit.async_set(power=True)
    assert len(emitter.sent) == 1 and unit.previous.temperature == 26.0


async def test_power_sensor_keeps_toggle_protocols_right(hass, emitter):
    # Kelon sends a power toggle when previous.power != target.power.
    unit = await make_unit(hass, emitter, "Kelon", "ON/OFF 9000-12000")
    await unit.async_set(power=True, mode="cool", temperature=24.0)
    on = unit.state
    unit.power_reported(False)  # someone pressed OFF on the remote
    assert unit.state.power is False and unit.previous.power is False
    await unit.async_set(power=True)  # HA turns it back on: must toggle
    toggled = unit.device.encode(replace(on, power=False), on)
    assert emitter.sent[-1][1] == to_raw(toggled.signal)
    unit.power_reported(False)
    unit.power_reported(True)  # remote ON
    await unit.async_set(temperature=25.0)  # must NOT toggle power
    plain = unit.device.encode(on, replace(on, temperature=25.0))
    wrong = unit.device.encode(replace(on, power=False), replace(on, temperature=25.0))
    assert to_raw(plain.signal) != to_raw(wrong.signal)
    assert emitter.sent[-1][1] == to_raw(plain.signal)


async def test_power_reported_does_not_send(hass, emitter):
    unit = await make_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    calls = []
    unit.add_listener(lambda: calls.append(1))
    unit.power_reported(True)
    unit.power_reported(True)  # no change: no notification
    assert emitter.sent == [] and unit.state.power is True and calls == [1]


async def test_failed_send_keeps_previous(hass, emitter):  # Review Focus 3
    unit = await make_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    await unit.async_set(power=True, mode="cool", temperature=24.0)
    before = unit.previous
    emitter.fail = True
    with pytest.raises(HomeAssistantError):
        await unit.async_set(temperature=20.0)
    assert unit.previous == before and unit.state.temperature == 24.0
    emitter.fail = False
    await unit.async_set(temperature=21.0)
    expected = unit.device.encode(before, replace(before, temperature=21.0))
    assert emitter.sent[-1][1] == to_raw(expected.signal)


async def test_action_is_sent_with_state(hass, emitter):
    unit = await make_unit(hass, emitter, "Airspool", "Mini-split")
    await unit.async_set(power=True, mode="cool", temperature=24.0)
    prev = unit.previous
    await unit.async_action("se_step")
    expected = unit.device.encode(prev, unit.state, actions=("se_step",))
    assert emitter.sent[-1][1] == to_raw(expected.signal)


async def test_state_survives_restart(hass, emitter, hass_storage):
    unit = await make_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    await unit.async_set(power=True, mode="heat", temperature=22.0, fan="3")
    again = await make_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    assert again.state == unit.state and again.previous == unit.previous


async def test_corrupt_store_is_normalised(hass, emitter, hass_storage):  # RF 2
    hass_storage["irhvac.u1"] = {
        "version": 1,
        "key": "irhvac.u1",
        "data": {
            "state": {
                "power": True,
                "mode": "cool",
                "temperature": 24.0,
                "fan": "9",  # not a level this model has
                "swing_v": "off",
                "swing_h": "off",
                "features": {},
            },
            "previous": {"power": "x"},
        },
    }
    unit = await make_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    assert unit.previous is None
    assert unit.state.fan in unit.capabilities.fan.values and unit.state.power is True


async def test_concurrent_sets_coalesce(hass, emitter):
    unit = await make_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    await unit.async_set(power=True, mode="cool", temperature=24.0)
    emitter.sent.clear()
    emitter.delay = 0.05
    await asyncio.gather(
        unit.async_set(temperature=20.0),
        unit.async_set(temperature=21.0),
        unit.async_set(temperature=22.0),
    )
    assert len(emitter.sent) == 2 and unit.state.temperature == 22.0


async def test_emitter_errors_reach_the_user_as_ha_errors(hass, emitter):
    unit = await make_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    emitter.error = OSError("network unreachable")
    with pytest.raises(HomeAssistantError, match="network unreachable"):
        await unit.async_set(power=True, mode="cool")
    assert unit.state.power is False and unit.previous is None
