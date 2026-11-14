"""The pyhvac-to-infrared transport."""

import pytest
from homeassistant.exceptions import HomeAssistantError
from pyhvac import registry
from pyhvac.ir.formats import to_raw
from pyhvac.state import HvacState

from custom_components.irhvac.transport import PyhvacCommand, async_send_signal


def _signal(brand, model, state):
    return registry.get_device(brand, model).encode(None, state).signal


async def test_command_carries_pyhvac_signal():
    signal = _signal("Mitsubishi Electric", "MSZ-GV2519", HvacState(True, "cool", 23.5))
    command = PyhvacCommand(signal)
    assert command.modulation == signal.carrier
    assert command.get_raw_timings() == to_raw(signal)
    assert command.get_raw_timings()[0] > 0 and command.get_raw_timings()[1] < 0


async def test_send_reaches_emitter(hass, emitter):
    signal = _signal("AEG", "Chillflex Pro AXP26U558HW", HvacState(True, "heat", 24.0))
    await async_send_signal(hass, emitter.entity_id, signal)
    assert emitter.sent == [(38000, to_raw(signal))]


async def test_send_to_missing_emitter_raises(hass, emitter):
    signal = _signal("AEG", "Chillflex Pro AXP26U558HW", HvacState(True, "heat", 24.0))
    with pytest.raises(HomeAssistantError):
        await async_send_signal(hass, "infrared.nope", signal)
    assert emitter.sent == []
