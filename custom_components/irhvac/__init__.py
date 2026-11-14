"""IR HVAC: infrared-controlled air conditioners, encoded by pyhvac.

One config entry; each A/C unit is a config subentry of it.
"""

from __future__ import annotations

from functools import partial
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_BRAND, CONF_EMITTER, CONF_MODEL, SUBENTRY_UNIT
from .unit import IrHvacUnit, unit_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]

type IrHvacConfigEntry = ConfigEntry[dict[str, IrHvacUnit]]


async def async_setup_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Set up every A/C unit of the entry."""
    units: dict[str, IrHvacUnit] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_UNIT:
            continue
        data = subentry.data
        try:
            unit = IrHvacUnit(
                hass,
                subentry_id,
                data[CONF_BRAND],
                data[CONF_MODEL],
                data[CONF_EMITTER],
            )
        except ConfigEntryError as err:
            _LOGGER.error("Skipping unit %s: %s", subentry.title, err)
            continue
        await unit.async_load()
        units[subentry_id] = unit
    entry.runtime_data = units
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        entry.add_update_listener(partial(_async_updated, set(entry.subentries)))
    )
    return True


async def _async_updated(
    known: set[str], hass: HomeAssistant, entry: IrHvacConfigEntry
) -> None:
    """A unit was added, reconfigured or deleted: forget deleted ones, reload."""
    for subentry_id in known - set(entry.subentries):
        await unit_store(hass, subentry_id).async_remove()
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Unload every unit, once its send in progress is done."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    for unit in entry.runtime_data.values():
        await unit.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> None:
    """Forget every unit's stored state."""
    for subentry_id in entry.subentries:
        await unit_store(hass, subentry_id).async_remove()
