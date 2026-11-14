"""Switch, select and button entities for features and actions."""

from dataclasses import replace

from homeassistant.components.climate import HVACMode
from homeassistant.helpers import entity_registry as er
from pyhvac.ir.formats import to_raw

from .conftest import add_unit


def entity_id(hass, domain, unique_id):
    return er.async_get(hass).async_get_entity_id(domain, "irhvac", unique_id)


async def turn_on(hass, entry):
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            "entity_id": entity_id(hass, "climate", entry.entry_id),
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )


async def test_daikin_feature_entities(hass, emitter):
    entry = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    for feature in ("quiet", "light", "purifier", "cleaning"):
        assert entity_id(hass, "switch", f"{entry.entry_id}_{feature}")
    assert not entity_id(hass, "switch", f"{entry.entry_id}_powerful")  # a preset
    await turn_on(hass, entry)
    unit = entry.runtime_data
    before = unit.previous
    light = entity_id(hass, "switch", f"{entry.entry_id}_light")
    assert hass.states.get(light).name.endswith("Display light")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": light}, blocking=True
    )
    target = replace(before, features={**before.features, "light": True})
    assert emitter.sent[-1][1] == to_raw(unit.device.encode(before, target).signal)
    assert hass.states.get(light).state == "on"


async def test_economy_levels_select(hass, emitter):
    entry = await add_unit(hass, emitter, "LG", "Dual Inverter")
    sel = entity_id(hass, "select", f"{entry.entry_id}_economy")
    assert hass.states.get(sel).attributes["options"] == ["off", "80", "60", "40"]
    await hass.services.async_call(
        "select", "select_option", {"entity_id": sel, "option": "60"}, blocking=True
    )
    assert entry.runtime_data.state.features["economy"] == "60"
    assert hass.states.get(sel).state == "60"


async def test_feature_change_while_off_is_stored(hass, emitter):
    entry = await add_unit(hass, emitter, "Daikin", "FTXM20R5V1B")
    light = entity_id(hass, "switch", f"{entry.entry_id}_light")
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": light}, blocking=True
    )
    assert emitter.sent == [] and entry.runtime_data.state.features["light"] is True
    await turn_on(hass, entry)
    assert len(emitter.sent) == 1 and entry.runtime_data.previous.features["light"]


async def test_unknown_feature_gets_a_readable_name(hass, emitter, monkeypatch):
    from custom_components.irhvac import switch

    monkeypatch.setattr(switch, "extra_features", lambda caps: (["fresh_air"], []))
    entry = await add_unit(hass, emitter, "AEG", "Chillflex Pro AXP26U338CW")
    eid = entity_id(hass, "switch", f"{entry.entry_id}_fresh_air")
    assert hass.states.get(eid).name.endswith("Fresh air")


async def test_action_button_sends_action(hass, emitter):
    entry = await add_unit(hass, emitter, "Airspool", "Mini-split")
    await turn_on(hass, entry)
    unit = entry.runtime_data
    before = unit.previous
    button = entity_id(hass, "button", f"{entry.entry_id}_action_se_step")
    assert hass.states.get(button).name.endswith("SE speed step")
    await hass.services.async_call(
        "button", "press", {"entity_id": button}, blocking=True
    )
    expected = unit.device.encode(before, unit.state, actions=("se_step",))
    assert emitter.sent[-1][1] == to_raw(expected.signal)
