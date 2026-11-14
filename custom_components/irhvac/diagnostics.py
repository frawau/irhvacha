"""Diagnostics: what the unit is, can do, and last sent."""

from __future__ import annotations

from typing import Any

import pyhvac
from homeassistant.core import HomeAssistant

from . import IrHvacConfigEntry
from .mapping import options, state_to_dict


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrHvacConfigEntry
) -> dict[str, Any]:
    """Diagnostics for one unit (nothing in it is secret)."""
    unit = entry.runtime_data
    caps = unit.capabilities

    def choice(c):
        return None if c is None else options(c)

    return {
        "entry": {"data": dict(entry.data), "options": dict(entry.options)},
        "pyhvac": pyhvac.__version__,
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
