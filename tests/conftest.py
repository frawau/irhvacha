"""Shared fixtures: a fake infrared emitter on the real infrared component."""

import custom_components.irhvac  # noqa: F401  (HA must load ours, not the plugin's bundled package)
import pytest
from homeassistant.components.infrared import InfraredEmitterEntity
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/irhvac."""
    yield


class FakeEmitter(InfraredEmitterEntity):
    """Records what it is asked to send; raises when ``fail`` is set."""

    _attr_unique_id = "fake_emitter"
    _attr_name = "Fake emitter"

    def __init__(self):
        self.sent: list[tuple[int, list[int]]] = []
        self.fail = False

    async def async_send_command(self, command):
        if self.fail:
            raise HomeAssistantError("emitter offline")
        self.sent.append((command.modulation, command.get_raw_timings()))


@pytest.fixture
async def emitter(hass):
    """A FakeEmitter registered in the infrared component."""
    assert await async_setup_component(hass, "infrared", {})
    fake = FakeEmitter()
    await hass.data[DATA_COMPONENT].async_add_entities([fake])
    await hass.async_block_till_done()
    return fake
