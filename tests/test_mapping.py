"""Mapping between pyhvac capabilities/states and HA climate concepts."""

import pytest
from homeassistant.components.climate import HVACMode
from pyhvac import registry
from pyhvac.state import HvacState

from custom_components.irhvac.mapping import (
    extra_features,
    hvac_modes,
    option_of,
    options,
    preset_modes,
    preset_of,
    pyhvac_mode,
    state_from_dict,
    state_to_dict,
    target_step,
    value_of,
    with_preset,
)


def caps(brand, model):
    return registry.get_device(brand, model).capabilities


def test_modes_and_step():
    c = caps("Mitsubishi Electric", "MSZ-GV2519")
    assert hvac_modes(c)[0] is HVACMode.OFF
    assert set(hvac_modes(c)) == {
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.HEAT,
    }
    assert target_step(c) == 0.5
    assert target_step(caps("Mitsubishi Electric", "PAR-FA32MA")) == 1.0


def test_pyhvac_mode_round_trip():
    assert pyhvac_mode(HVACMode.FAN_ONLY) == "fan"
    assert pyhvac_mode(HVACMode.AUTO) == "auto"
    with pytest.raises(ValueError):
        pyhvac_mode(HVACMode.OFF)


def test_fan_options_use_labels():
    c = caps("AEG", "Chillflex Pro AXP26U338CW")
    assert options(c.fan) == ["auto", "low", "medium", "high"]
    assert value_of(c.fan, "high") == "3" and option_of(c.fan, "1") == "low"
    with pytest.raises(ValueError):
        value_of(c.fan, "turbo")


def test_presets_and_extras_split_daikin():
    c = caps("Daikin", "FTXM20R5V1B")
    assert preset_modes(c) == ["none", "boost", "eco"]
    switches, selects = extra_features(c)
    assert switches == ["quiet", "light", "purifier", "cleaning"] and selects == []


def test_economy_levels_is_a_select_not_eco():
    c = caps("LG", "Dual Inverter")  # economy off/80/60/40
    assert "eco" not in (preset_modes(c) or [])
    assert "economy" in extra_features(c)[1]


def test_no_presets_gives_none():
    assert preset_modes(caps("Airwell", "DC Series")) is None


def test_presets_are_exclusive():
    c = caps("Daikin", "FTXM20R5V1B")
    s = with_preset(HvacState(True, "cool", 24.0), c, "boost")
    s = with_preset(s, c, "eco")
    assert s.features["economy"] is True and s.features["powerful"] is False
    assert preset_of(s, c) == "eco"
    assert preset_of(with_preset(s, c, "none"), c) == "none"
    with pytest.raises(ValueError):
        with_preset(s, c, "sleep")  # this model has no sleep


def test_state_round_trip():
    s = HvacState(
        True, "heat", 22.5, fan="2", features={"economy": "60", "light": True}
    )
    assert state_from_dict(state_to_dict(s)) == s
