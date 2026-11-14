"""One-shot actions (pyhvac capabilities.actions)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrHvacConfigEntry
from .entity import IrHvacNamedEntity
from .unit import IrHvacUnit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One button per action."""
    for subentry_id, unit in entry.runtime_data.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            (
                IrHvacActionButton(subentry, unit, name, label)
                for name, label in unit.capabilities.actions.items()
            ),
            config_subentry_id=subentry_id,
        )


class IrHvacActionButton(IrHvacNamedEntity, ButtonEntity):
    """Send a pyhvac action."""

    def __init__(
        self, subentry: ConfigSubentry, unit: IrHvacUnit, action: str, label: str
    ) -> None:
        super().__init__(subentry, unit, action, label)
        self.action = action
        self._attr_unique_id = f"{subentry.subentry_id}_action_{action}"

    async def async_press(self) -> None:
        await self.unit.async_action(self.action, context=self._context)
