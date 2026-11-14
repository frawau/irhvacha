"""IR HVAC: infrared-controlled air conditioners, encoded by pyhvac.

One config entry; each A/C unit is a config subentry of it.
"""

from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store

from .const import (
    CONF_BRAND,
    CONF_EMITTER,
    CONF_MODEL,
    DOMAIN,
    STORAGE_VERSION,
    SUBENTRY_UNIT,
)
from .unit import IrHvacUnit, unit_store

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]

type IrHvacConfigEntry = ConfigEntry[dict[str, IrHvacUnit]]


def _index(hass: HomeAssistant) -> Store:
    """The ids of the units that have a store, to clean up deleted ones."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.units")


def _units(entry: IrHvacConfigEntry) -> dict[str, Any]:
    """What a reload depends on: each unit's title and data."""
    return {
        subentry_id: (subentry.title, dict(subentry.data))
        for subentry_id, subentry in entry.subentries.items()
    }


async def _async_forget_deleted(hass: HomeAssistant, entry: IrHvacConfigEntry):
    """Remove the stores of units deleted since the last setup."""
    index = _index(hass)
    known = set(await index.async_load() or [])
    for unit_id in known - set(entry.subentries):
        await unit_store(hass, unit_id).async_remove()
    await index.async_save(sorted(entry.subentries))


async def async_setup_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Set up every A/C unit of the entry."""
    await _async_forget_deleted(hass, entry)
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
        entry.add_update_listener(partial(_async_updated, _units(entry)))
    )
    return True


async def _async_updated(
    loaded: dict[str, Any], hass: HomeAssistant, entry: IrHvacConfigEntry
) -> None:
    """A unit was added, reconfigured or deleted: reload (setup forgets the
    deleted ones). Other changes, such as renaming the entry, need nothing."""
    if _units(entry) != loaded:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> bool:
    """Unload every unit, once its send in progress is done."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    for unit in entry.runtime_data.values():
        await unit.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: IrHvacConfigEntry) -> None:
    """Forget every unit's stored state."""
    index = _index(hass)
    for unit_id in set(await index.async_load() or []) | set(entry.subentries):
        await unit_store(hass, unit_id).async_remove()
    await index.async_remove()
