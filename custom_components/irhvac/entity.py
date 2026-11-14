"""Base entity: one device per unit, available while its emitter is."""

from __future__ import annotations

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .unit import IrHvacUnit


class IrHvacEntity(InfraredEmitterConsumerEntity):
    """An entity showing (part of) an IrHvacUnit."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unit: IrHvacUnit) -> None:
        self.unit = unit
        self._infrared_emitter_entity_id = unit.emitter
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=unit.brand,
            model=unit.model,
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        """Follow the unit's state."""
        await super().async_added_to_hass()
        self.async_on_remove(self.unit.add_listener(self.async_write_ha_state))
