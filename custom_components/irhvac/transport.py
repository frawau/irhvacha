"""Sending pyhvac signals through Home Assistant's infrared building block.

This is the only module that knows how a signal leaves Home Assistant; an
RF transmitter would be a second kind here, with no change to the entities.
"""

from __future__ import annotations

from homeassistant.components import infrared
from homeassistant.core import Context, HomeAssistant
from infrared_protocols.commands import Command
from pyhvac.ir.formats import to_raw


class PyhvacCommand(Command):
    """An infrared-protocols command carrying a pyhvac signal."""

    def __init__(self, signal) -> None:
        super().__init__(modulation=signal.carrier)
        self._timings = to_raw(signal)

    def get_raw_timings(self) -> list[int]:
        """Signed µs: marks positive, spaces negative."""
        return list(self._timings)


async def async_send_signal(
    hass: HomeAssistant,
    emitter_entity_id: str,
    signal,
    context: Context | None = None,
) -> None:
    """Send ``signal`` through the emitter; HomeAssistantError if it can't."""
    await infrared.async_send_command(
        hass, emitter_entity_id, PyhvacCommand(signal), context=context
    )
