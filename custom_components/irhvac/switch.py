"""On/off features that are not presets (light, cleaning, ...)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrHvacConfigEntry
from .entity import IrHvacNamedEntity
from .mapping import extra_features


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One switch per on/off feature."""
    switches, _ = extra_features(entry.runtime_data.capabilities)
    async_add_entities(IrHvacFeatureSwitch(entry, feature) for feature in switches)


class IrHvacFeatureSwitch(IrHvacNamedEntity, SwitchEntity):
    """A pyhvac on/off feature."""

    def __init__(self, entry: IrHvacConfigEntry, feature: str) -> None:
        super().__init__(
            entry,
            entry.runtime_data,
            feature,
            feature.replace("_", " ").capitalize(),
        )
        self.feature = feature
        self._attr_unique_id = f"{entry.entry_id}_{feature}"

    @property
    def is_on(self) -> bool:
        return self.unit.state.features.get(self.feature) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.unit.async_set(context=self._context, features={self.feature: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.unit.async_set(context=self._context, features={self.feature: False})
