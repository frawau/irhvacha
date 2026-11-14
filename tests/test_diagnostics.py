"""Config entry and device diagnostics."""

import pyhvac
from homeassistant.components.climate import HVACMode
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.irhvac.const import DOMAIN
from custom_components.irhvac.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

from .conftest import add_unit


async def test_diagnostics_snapshot(hass, emitter):
    added = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    other = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    eid = er.async_get(hass).async_get_entity_id("climate", DOMAIN, added.id)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": eid, "temperature": 22, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    diag = await async_get_config_entry_diagnostics(hass, added.entry)
    assert diag["pyhvac"] == pyhvac.__version__
    assert set(diag["units"]) == {added.id, other.id}
    unit = diag["units"][added.id]
    assert set(unit) == {"title", "data", "capabilities", "state", "previous"}
    assert unit["title"] == "AEG Chillflex Pro AXP26U558HW"
    assert unit["data"] == {
        "brand": "AEG",
        "model": "Chillflex Pro AXP26U558HW",
        "emitter": emitter.entity_id,
    }
    caps = unit["capabilities"]
    assert caps["modes"] == ["auto", "cool", "fan", "dry", "heat"]
    assert caps["temperature"] == {"min": 16.0, "max": 32.0, "decimals": [0]}
    assert caps["fan"] == ["auto", "low", "medium", "high"]
    assert caps["actions"] == []
    assert unit["state"]["mode"] == "heat" and unit["state"]["temperature"] == 22.0
    assert unit["previous"] == unit["state"]

    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, added.id), added.entry.entry_id
    )
    one = await async_get_device_diagnostics(hass, added.entry, device)
    assert one == {"pyhvac": pyhvac.__version__, "unit": unit}
