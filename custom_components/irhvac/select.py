"""Features with levels (economy 80/60/40, auto bias, spot, ...)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrHvacConfigEntry
from .entity import IrHvacNamedEntity
from .mapping import extra_features, option_of, options, value_of


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """One select per feature with levels."""
    _, selects = extra_features(entry.runtime_data.capabilities)
    async_add_entities(IrHvacFeatureSelect(entry, feature) for feature in selects)


class IrHvacFeatureSelect(IrHvacNamedEntity, SelectEntity):
    """A pyhvac feature with levels."""

    def __init__(self, entry: IrHvacConfigEntry, feature: str) -> None:
        super().__init__(
            entry,
            entry.runtime_data,
            feature,
            feature.replace("_", " ").capitalize(),
        )
        self.feature = feature
        self.choice = self.unit.capabilities.features[feature]
        self._attr_unique_id = f"{entry.entry_id}_{feature}"
        self._attr_options = options(self.choice)

    @property
    def current_option(self) -> str | None:
        value = self.unit.state.features.get(self.feature, self.choice.values[0])
        return option_of(self.choice, value)

    async def async_select_option(self, option: str) -> None:
        await self.unit.async_set(
            context=self._context,
            features={self.feature: value_of(self.choice, option)},
        )
