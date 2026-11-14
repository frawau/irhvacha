"""Config entry diagnostics."""

import pyhvac
from homeassistant.components.climate import HVACMode
from homeassistant.helpers import entity_registry as er

from custom_components.irhvac.diagnostics import async_get_config_entry_diagnostics

from .conftest import add_unit


async def test_diagnostics_snapshot(hass, emitter):
    entry = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U558HW")
    eid = er.async_get(hass).async_get_entity_id("climate", "irhvac", entry.entry_id)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": eid, "temperature": 22, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert set(diag) == {"entry", "pyhvac", "capabilities", "state", "previous"}
    assert diag["pyhvac"] == pyhvac.__version__
    assert diag["entry"] == {
        "data": {"brand": "AEG", "model": "Chillflex Pro AXP26U558HW"},
        "options": {"emitter": emitter.entity_id},
    }
    caps = diag["capabilities"]
    assert caps["modes"] == ["auto", "cool", "fan", "dry", "heat"]
    assert caps["temperature"] == {"min": 16.0, "max": 32.0, "decimals": [0]}
    assert caps["fan"] == ["auto", "low", "medium", "high"]
    assert caps["actions"] == []
    assert diag["state"]["mode"] == "heat" and diag["state"]["temperature"] == 22.0
    assert diag["previous"] == diag["state"]
