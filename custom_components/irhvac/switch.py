"""On/off features that are not presets (light, cleaning, ...)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrHvacConfigEntry
from .entity import IrHvacNamedEntity
from .mapping import extra_features
from .unit import IrHvacUnit


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One switch per on/off feature."""
    for subentry_id, unit in entry.runtime_data.items():
        switches, _ = extra_features(unit.capabilities)
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            (IrHvacFeatureSwitch(subentry, unit, feature) for feature in switches),
            config_subentry_id=subentry_id,
        )


class IrHvacFeatureSwitch(IrHvacNamedEntity, SwitchEntity):
    """A pyhvac on/off feature."""

    def __init__(
        self, subentry: ConfigSubentry, unit: IrHvacUnit, feature: str
    ) -> None:
        super().__init__(
            subentry, unit, feature, feature.replace("_", " ").capitalize()
        )
        self.feature = feature
        self._attr_unique_id = f"{subentry.subentry_id}_{feature}"

    @property
    def is_on(self) -> bool:
        return self.unit.state.features.get(self.feature) is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.unit.async_set(context=self._context, features={self.feature: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.unit.async_set(context=self._context, features={self.feature: False})
