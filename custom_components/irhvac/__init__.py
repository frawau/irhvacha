"""IR HVAC: infrared-controlled air conditioners, encoded by pyhvac."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import CONF_BRAND, CONF_EMITTER, CONF_MODEL, STORAGE_VERSION
from .unit import IrHvacUnit

PLATFORMS: list[Platform] = []

type IrHvacConfigEntry = ConfigEntry[IrHvacUnit]


async def async_setup_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Set up one A/C unit."""
    unit = IrHvacUnit(
        hass,
        entry.entry_id,
        entry.data[CONF_BRAND],
        entry.data[CONF_MODEL],
        entry.options[CONF_EMITTER],
    )
    await unit.async_load()
    entry.runtime_data = unit
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: IrHvacConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Unload one A/C unit."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> None:
    """Forget the unit's stored state."""
    await Store(hass, STORAGE_VERSION, f"irhvac.{entry.entry_id}").async_remove()
