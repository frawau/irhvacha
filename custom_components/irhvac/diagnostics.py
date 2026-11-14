"""Diagnostics: what each unit is, can do, and last sent."""

from __future__ import annotations

from typing import Any

import pyhvac
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import IrHvacConfigEntry
from .const import DOMAIN
from .mapping import options, state_to_dict
from .unit import IrHvacUnit


def _unit(entry: IrHvacConfigEntry, unit_id: str, unit: IrHvacUnit) -> dict:
    caps = unit.capabilities
    subentry = entry.subentries[unit_id]

    def choice(c):
        return None if c is None else options(c)

    return {
        "title": subentry.title,
        "data": dict(subentry.data),
        "capabilities": {
            "modes": list(caps.modes),
            "temperature": {
                "min": caps.temperature.min,
                "max": caps.temperature.max,
                "decimals": list(caps.temperature.decimals),
            },
            "fan": choice(caps.fan),
            "swing_v": choice(caps.swing_v),
            "swing_h": choice(caps.swing_h),
            "features": {name: options(c) for name, c in caps.features.items()},
            "actions": list(caps.actions),
        },
        "state": state_to_dict(unit.state),
        "previous": None if unit.previous is None else state_to_dict(unit.previous),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrHvacConfigEntry
) -> dict[str, Any]:
    """Diagnostics for every unit (nothing in them is secret)."""
    return {
        "pyhvac": pyhvac.__version__,
        "units": {
            unit_id: _unit(entry, unit_id, unit)
            for unit_id, unit in entry.runtime_data.items()
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: IrHvacConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Diagnostics for the unit of ``device``."""
    unit_id = next(i for d, i in device.identifiers if d == DOMAIN)
    return {
        "pyhvac": pyhvac.__version__,
        "unit": _unit(entry, unit_id, entry.runtime_data[unit_id]),
    }
