"""The climate entity of a unit."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_ON,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import TemperatureConverter

from . import IrHvacConfigEntry
from .const import CONF_HUMIDITY_SENSOR, CONF_POWER_SENSOR, CONF_TEMPERATURE_SENSOR
from .entity import IrHvacEntity
from .mapping import (
    HVAC_MODES,
    hvac_modes,
    option_of,
    options,
    preset_modes,
    preset_of,
    pyhvac_mode,
    setpoint,
    target_step,
    value_of,
    with_preset,
)
from .unit import IrHvacUnit

_TEMPERATURE_UNITS = {unit.value for unit in UnitOfTemperature}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrHvacConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add each unit's climate entity."""
    for subentry_id, unit in entry.runtime_data.items():
        async_add_entities(
            [IrHvacClimate(entry.subentries[subentry_id], unit)],
            config_subentry_id=subentry_id,
        )


def _number(state: State | None) -> float | None:
    if state is None:
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


class IrHvacClimate(IrHvacEntity, ClimateEntity):
    """Modes, setpoint, fan, swings and presets of one A/C unit."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, subentry: ConfigSubentry, unit: IrHvacUnit) -> None:
        super().__init__(subentry, unit)
        caps = unit.capabilities
        self._attr_unique_id = subentry.subentry_id
        self._sensors = {
            key: subentry.data.get(key)
            for key in (
                CONF_TEMPERATURE_SENSOR,
                CONF_HUMIDITY_SENSOR,
                CONF_POWER_SENSOR,
            )
        }
        self._attr_hvac_modes = hvac_modes(caps)
        self._attr_min_temp = caps.temperature.min
        self._attr_max_temp = caps.temperature.max
        self._attr_target_temperature_step = target_step(caps)
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if caps.fan is not None:
            self._attr_fan_modes = options(caps.fan)
            features |= ClimateEntityFeature.FAN_MODE
        if caps.swing_v is not None:
            self._attr_swing_modes = options(caps.swing_v)
            features |= ClimateEntityFeature.SWING_MODE
        if caps.swing_h is not None:
            self._attr_swing_horizontal_modes = options(caps.swing_h)
            features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        if presets := preset_modes(caps):
            self._attr_preset_modes = presets
            features |= ClimateEntityFeature.PRESET_MODE
        self._attr_supported_features = features

    # -- state, from the unit -------------------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        state = self.unit.state
        return HVAC_MODES[state.mode] if state.power else HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        return self.unit.state.temperature

    @property
    def fan_mode(self) -> str | None:
        fan = self.unit.capabilities.fan
        return None if fan is None else option_of(fan, self.unit.state.fan)

    @property
    def swing_mode(self) -> str | None:
        swing = self.unit.capabilities.swing_v
        return None if swing is None else option_of(swing, self.unit.state.swing_v)

    @property
    def swing_horizontal_mode(self) -> str | None:
        swing = self.unit.capabilities.swing_h
        return None if swing is None else option_of(swing, self.unit.state.swing_h)

    @property
    def preset_mode(self) -> str | None:
        if not self._attr_supported_features & ClimateEntityFeature.PRESET_MODE:
            return None
        return preset_of(self.unit.state, self.unit.capabilities)

    # -- commands ---------------------------------------------------------------

    async def _set(self, **changes: Any) -> None:
        await self.unit.async_set(context=self._context, **changes)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._set(power=False)
        else:
            await self._set(power=True, mode=pyhvac_mode(hvac_mode))

    async def async_turn_on(self) -> None:
        await self._set(power=True)

    async def async_turn_off(self) -> None:
        await self._set(power=False)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        changes: dict[str, Any] = {}
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            changes["temperature"] = self._setpoint(float(temperature))
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            if hvac_mode == HVACMode.OFF:
                changes["power"] = False
            else:
                changes.update(power=True, mode=pyhvac_mode(hvac_mode))
        await self._set(**changes)

    def _setpoint(self, celsius: float) -> float:
        """The setpoint for a request; a step the user sees never sticks.

        HA steps °F displays by whole degrees, which can snap back onto the
        current °C setpoint: then the next setpoint that way is taken.
        """
        current = self.unit.state.temperature
        shown_unit = self.hass.config.units.temperature_unit
        if shown_unit == UnitOfTemperature.CELSIUS:
            return celsius
        to_shown = TemperatureConverter.converter_factory(
            UnitOfTemperature.CELSIUS, shown_unit
        )
        if round(to_shown(celsius)) == round(to_shown(current)):
            return current
        return setpoint(self.unit.capabilities, current, celsius)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._set(fan=value_of(self.unit.capabilities.fan, fan_mode))

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self._set(swing_v=value_of(self.unit.capabilities.swing_v, swing_mode))

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        await self._set(
            swing_h=value_of(self.unit.capabilities.swing_h, swing_horizontal_mode)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        state = with_preset(self.unit.state, self.unit.capabilities, preset_mode)
        await self._set(features=dict(state.features))

    # -- sensors ----------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        tracked = [s for s in self._sensors.values() if s]
        if tracked:
            self.async_on_remove(
                async_track_state_change_event(self.hass, tracked, self._sensor_changed)
            )
        for key in (CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR):
            if self._sensors[key]:
                self._read(key, self.hass.states.get(self._sensors[key]))
        if power := self._sensors[CONF_POWER_SENSOR]:
            self._power(self.hass.states.get(power))

    @callback
    def _sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        if entity_id == self._sensors[CONF_POWER_SENSOR]:
            self._power(new_state)
            return
        for key in (CONF_TEMPERATURE_SENSOR, CONF_HUMIDITY_SENSOR):
            if entity_id == self._sensors[key]:
                self._read(key, new_state)
        self.async_write_ha_state()

    @callback
    def _power(self, state: State | None) -> None:
        if state is not None and state.state in (STATE_ON, STATE_OFF):
            self.unit.power_reported(state.state == STATE_ON)

    @callback
    def _read(self, key: str, state: State | None) -> None:
        value = _number(state)
        if key == CONF_HUMIDITY_SENSOR:
            self._attr_current_humidity = value
            return
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        if (
            value is not None
            and unit in _TEMPERATURE_UNITS
            and unit != UnitOfTemperature.CELSIUS
        ):
            value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        self._attr_current_temperature = value
