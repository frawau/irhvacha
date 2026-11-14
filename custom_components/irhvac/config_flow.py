"""Config flow: the integration once; a subentry flow per A/C unit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import infrared
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from pyhvac import brands as pyhvac_brands
from pyhvac import registry

from .const import (
    CONF_BRAND,
    CONF_EMITTER,
    CONF_HUMIDITY_SENSOR,
    CONF_MODEL,
    CONF_POWER_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    SUBENTRY_UNIT,
)

_REMOTES = {
    (brand, model)
    for brand, model, kind, *_ in pyhvac_brands.MODELS
    if kind == "remote"
}


def _model_options(brand: str) -> list[SelectOptionDict]:
    return [
        SelectOptionDict(
            value=model,
            label=f"{model} (remote)" if (brand, model) in _REMOTES else model,
        )
        for model in registry.models(brand)
    ]


def _unit_fields(emitters: list[str], current: dict[str, Any]) -> dict:
    """The emitter and optional sensor fields, prefilled from ``current``."""

    def optional(key):
        if key in current:
            return vol.Optional(key, description={"suggested_value": current[key]})
        return vol.Optional(key)

    emitter_key = (
        vol.Required(CONF_EMITTER, default=current[CONF_EMITTER])
        if CONF_EMITTER in current
        else vol.Required(CONF_EMITTER)
    )
    return {
        emitter_key: EntitySelector(EntitySelectorConfig(include_entities=emitters)),
        optional(CONF_TEMPERATURE_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        optional(CONF_HUMIDITY_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="humidity")
        ),
        optional(CONF_POWER_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="binary_sensor")
        ),
    }


def _unique_id(data: dict[str, Any]) -> str:
    return f"{data[CONF_EMITTER]}|{data[CONF_BRAND]}|{data[CONF_MODEL]}"


class IrHvacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add the integration (once); units are added as subentries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nothing to ask."""
        return self.async_create_entry(title="IR HVAC", data={})

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """A/C units."""
        return {SUBENTRY_UNIT: UnitSubentryFlow}


class UnitSubentryFlow(ConfigSubentryFlow):
    """Add an A/C unit, or change its emitter and sensors."""

    def __init__(self) -> None:
        self._brand: str | None = None

    def _taken(self, unique_id: str, but: str | None = None) -> bool:
        return any(
            sub.unique_id == unique_id and sub.subentry_id != but
            for sub in self._get_entry().subentries.values()
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the brand."""
        if not infrared.async_get_emitters(self.hass):
            return self.async_abort(reason="no_emitters")
        if user_input is not None:
            self._brand = user_input[CONF_BRAND]
            return await self.async_step_device()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BRAND): SelectSelector(
                        SelectSelectorConfig(
                            options=registry.brands(),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the model, the emitter and optional sensors."""
        brand = self._brand
        if user_input is not None and CONF_MODEL in user_input:
            data = {CONF_BRAND: brand, **user_input}
            unique_id = _unique_id(data)
            if self._taken(unique_id):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=f"{brand} {data[CONF_MODEL]}", data=data, unique_id=unique_id
            )
        emitters = infrared.async_get_emitters(self.hass)
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=_model_options(brand),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    **_unit_fields(emitters, {}),
                }
            ),
            description_placeholders={"brand": brand},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change the emitter and sensors (brand/model: re-add the unit)."""
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            data = {
                CONF_BRAND: subentry.data[CONF_BRAND],
                CONF_MODEL: subentry.data[CONF_MODEL],
                **user_input,
            }
            unique_id = _unique_id(data)
            if self._taken(unique_id, but=subentry.subentry_id):
                return self.async_abort(reason="already_configured")
            return self.async_update_and_abort(
                self._get_entry(), subentry, data=data, unique_id=unique_id
            )
        emitters = infrared.async_get_emitters(self.hass)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(_unit_fields(emitters, dict(subentry.data))),
            description_placeholders={"unit": subentry.title},
        )
