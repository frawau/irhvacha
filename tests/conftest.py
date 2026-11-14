"""Shared fixtures: a fake infrared emitter on the real infrared component."""

import custom_components.irhvac  # noqa: F401  (HA must load ours, not the plugin's bundled package)
import asyncio

import pytest
from homeassistant.components.infrared import InfraredEmitterEntity
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irhvac.const import CONF_BRAND, CONF_EMITTER, CONF_MODEL, DOMAIN
from custom_components.irhvac.unit import IrHvacUnit

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let HA load custom_components/irhvac."""
    yield


class FakeEmitter(InfraredEmitterEntity):
    """Records what it is asked to send; raises when ``fail`` is set."""

    def __init__(self, name="Fake emitter"):
        self._attr_name = name
        self._attr_unique_id = name.lower().replace(" ", "_")
        self.sent: list[tuple[int, list[int]]] = []
        self.fail = False
        self.delay = 0.0

    async def async_send_command(self, command):
        if self.delay:
            await asyncio.sleep(self.delay)
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


async def make_unit(hass, emitter, brand, model, entry_id="e1") -> IrHvacUnit:
    """An IrHvacUnit on the fake emitter, loaded from storage."""
    unit = IrHvacUnit(hass, entry_id, brand, model, emitter.entity_id)
    await unit.async_load()
    return unit


async def add_unit(
    hass, emitter, brand="Mitsubishi Electric", model="MSZ-GV2519", **options
) -> MockConfigEntry:
    """A set-up config entry for one unit."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{brand} {model}",
        data={CONF_BRAND: brand, CONF_MODEL: model},
        options={CONF_EMITTER: emitter.entity_id, **options},
        unique_id=f"{emitter.entity_id}|{brand}|{model}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
