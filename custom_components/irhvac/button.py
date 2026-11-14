"""One-shot actions (pyhvac capabilities.actions)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrHvacConfigEntry
from .entity import IrHvacNamedEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One button per action."""
    actions = entry.runtime_data.capabilities.actions
    async_add_entities(
        IrHvacActionButton(entry, name, label) for name, label in actions.items()
    )


class IrHvacActionButton(IrHvacNamedEntity, ButtonEntity):
    """Send a pyhvac action."""

    def __init__(self, entry: IrHvacConfigEntry, action: str, label: str) -> None:
        super().__init__(entry, entry.runtime_data, action, label)
        self.action = action
        self._attr_unique_id = f"{entry.entry_id}_action_{action}"

    async def async_press(self) -> None:
        await self.unit.async_action(self.action, context=self._context)
