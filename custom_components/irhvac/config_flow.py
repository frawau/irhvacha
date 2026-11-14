"""Config flow: brand, model, emitter and optional sensors; options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import infrared
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
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


class IrHvacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add one A/C unit."""

    VERSION = 1

    def __init__(self) -> None:
        self._brand: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Pick the model, the emitter and optional sensors."""
        brand = self._brand
        if user_input is not None and CONF_MODEL in user_input:
            model = user_input.pop(CONF_MODEL)
            await self.async_set_unique_id(
                f"{user_input[CONF_EMITTER]}|{brand}|{model}"
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{brand} {model}",
                data={CONF_BRAND: brand, CONF_MODEL: model},
                options=user_input,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Change the emitter and sensors."""
        return IrHvacOptionsFlow()


class IrHvacOptionsFlow(OptionsFlow):
    """Change the emitter and sensors of a unit (brand/model: re-add it)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The only step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        emitters = infrared.async_get_emitters(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                _unit_fields(emitters, dict(self.config_entry.options))
            ),
        )
