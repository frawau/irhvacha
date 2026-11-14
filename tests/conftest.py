"""Shared fixtures: a fake infrared emitter on the real infrared component."""

import custom_components.irhvac  # noqa: F401  (HA must load ours, not the plugin's bundled package)
import asyncio
from dataclasses import dataclass

import pytest
from homeassistant.components.infrared import InfraredEmitterEntity
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irhvac.const import (
    CONF_BRAND,
    CONF_EMITTER,
    CONF_MODEL,
    DOMAIN,
    SUBENTRY_UNIT,
)
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


async def make_unit(hass, emitter, brand, model, unit_id="u1") -> IrHvacUnit:
    """An IrHvacUnit on the fake emitter, loaded from storage."""
    unit = IrHvacUnit(hass, unit_id, brand, model, emitter.entity_id)
    await unit.async_load()
    return unit


def unit_subentry(brand, model, **data) -> dict:
    """``subentries_data`` for one unit."""
    return {
        "data": {CONF_BRAND: brand, CONF_MODEL: model, **data},
        "subentry_type": SUBENTRY_UNIT,
        "title": f"{brand} {model}",
        "unique_id": f"{data.get(CONF_EMITTER)}|{brand}|{model}",
    }


@dataclass
class Added:
    """A unit added by ``add_unit``: its entry, subentry id and unit."""

    entry: ConfigEntry
    id: str

    @property
    def unit(self) -> IrHvacUnit:
        return self.entry.runtime_data[self.id]


async def add_unit(
    hass, emitter, brand="Mitsubishi Electric", model="MSZ-GV2519", **options
) -> Added:
    """Add a unit to the IR HVAC entry (set up on first use)."""
    sub = unit_subentry(brand, model, **{CONF_EMITTER: emitter.entity_id, **options})
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        entry = MockConfigEntry(
            domain=DOMAIN, title="IR HVAC", data={}, subentries_data=[sub]
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return Added(entry, next(iter(entry.subentries)))
    entry = entries[0]
    subentry = ConfigSubentry(
        data=sub["data"],
        subentry_type=SUBENTRY_UNIT,
        title=sub["title"],
        unique_id=sub["unique_id"],
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    await hass.async_block_till_done()
    return Added(entry, subentry.subentry_id)
