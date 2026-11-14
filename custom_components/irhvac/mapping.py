"""Translate between pyhvac capabilities/states and Home Assistant climate."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.climate import HVACMode
from pyhvac.state import Capabilities, Choice, HvacState

HVAC_MODES: dict[str, HVACMode] = {
    "auto": HVACMode.AUTO,
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
}
_PYHVAC_MODES = {ha: name for name, ha in HVAC_MODES.items()}

# HA preset name -> pyhvac on/off feature it stands for.
PRESET_FEATURES: dict[str, str] = {
    "boost": "powerful",
    "eco": "economy",
    "sleep": "sleep",
}
PRESET_NONE = "none"


def hvac_modes(caps: Capabilities) -> list[HVACMode]:
    """OFF, then the model's modes in pyhvac's order."""
    return [HVACMode.OFF, *(HVAC_MODES[m] for m in caps.modes)]


def pyhvac_mode(mode: HVACMode) -> str:
    """The pyhvac mode for an HA mode other than OFF."""
    try:
        return _PYHVAC_MODES[mode]
    except KeyError:
        raise ValueError(f"no pyhvac mode for {mode!r}") from None


def target_step(caps: Capabilities) -> float:
    """The setpoint step, °C."""
    decimals = set(caps.temperature.decimals)
    if decimals == {0}:
        return 1.0
    if decimals == {0, 5}:
        return 0.5
    return 0.1


def options(choice: Choice) -> list[str]:
    """The choice's values as HA options: labels where pyhvac has them."""
    return [option_of(choice, value) for value in choice.values]


def option_of(choice: Choice, value) -> str:
    """The HA option for a pyhvac value."""
    return str(choice.labels.get(value, value))


def value_of(choice: Choice, option: str):
    """The pyhvac value for an HA option."""
    for value in choice.values:
        if option_of(choice, value) == option:
            return value
    raise ValueError(f"unknown option {option!r}: {options(choice)}")


def _is_on_off(choice: Choice) -> bool:
    return set(choice.values) == {False, True}


def preset_features(caps: Capabilities) -> dict[str, str]:
    """Presets this model has, mapped to their on/off features."""
    return {
        preset: feature
        for preset, feature in PRESET_FEATURES.items()
        if feature in caps.features and _is_on_off(caps.features[feature])
    }


def preset_modes(caps: Capabilities) -> list[str] | None:
    """``["none", *presets]``, or None when the model has no preset."""
    presets = preset_features(caps)
    return [PRESET_NONE, *presets] if presets else None


def preset_of(state: HvacState, caps: Capabilities) -> str:
    """The active preset (presets are exclusive), or "none"."""
    for preset, feature in preset_features(caps).items():
        if state.features.get(feature) is True:
            return preset
    return PRESET_NONE


def with_preset(state: HvacState, caps: Capabilities, preset: str) -> HvacState:
    """``state`` with ``preset`` on and the other presets off."""
    presets = preset_features(caps)
    if preset != PRESET_NONE and preset not in presets:
        raise ValueError(f"unknown preset {preset!r}: {preset_modes(caps)}")
    features = dict(state.features)
    for name, feature in presets.items():
        features[feature] = name == preset
    return replace(state, features=features)


def extra_features(caps: Capabilities) -> tuple[list[str], list[str]]:
    """Features that are not presets: (switches, selects), in pyhvac order."""
    presets = set(preset_features(caps).values())
    switches, selects = [], []
    for name, choice in caps.features.items():
        if name in presets:
            continue
        (switches if _is_on_off(choice) else selects).append(name)
    return switches, selects


def state_to_dict(state: HvacState) -> dict:
    """A JSON-safe dict of ``state``."""
    return {
        "power": state.power,
        "mode": state.mode,
        "temperature": state.temperature,
        "fan": state.fan,
        "swing_v": state.swing_v,
        "swing_h": state.swing_h,
        "features": dict(state.features),
    }


def state_from_dict(data: dict) -> HvacState:
    """The HvacState ``state_to_dict`` wrote."""
    return HvacState(
        power=data["power"],
        mode=data["mode"],
        temperature=data["temperature"],
        fan=data["fan"],
        swing_v=data["swing_v"],
        swing_h=data["swing_h"],
        features=dict(data["features"]),
    )
