"""One A/C unit: its pyhvac device, what it should do, what it was sent."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
import logging

from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.storage import Store
from pyhvac import registry
from pyhvac.state import HvacState

from .const import STORAGE_VERSION
from .mapping import state_from_dict, state_to_dict
from .transport import async_send_signal

_LOGGER = logging.getLogger(__name__)

DEFAULT_SETPOINT = 24.0  # °C


def unit_store(hass: HomeAssistant, unit_id: str) -> Store:
    """Where the unit ``unit_id`` keeps its state."""
    return Store(hass, STORAGE_VERSION, f"irhvac.{unit_id}")


class IrHvacUnit:
    """Desired state, last-sent ("previous") state, persistence and sending.

    ``state`` is what HA shows; its power is the unit's believed power.
    ``previous`` is what was last sent, with its power following the power
    sensor, so protocols with a power toggle stay right.
    """

    def __init__(
        self, hass: HomeAssistant, unit_id: str, brand: str, model: str, emitter: str
    ) -> None:
        try:
            self.device = registry.get_device(brand, model)
        except KeyError:
            raise ConfigEntryError(
                f"pyhvac has no model {model!r} for {brand!r}"
            ) from None
        self.hass = hass
        self.brand = brand
        self.model = model
        self.emitter = emitter
        self.capabilities = self.device.capabilities
        self.state: HvacState = self._default_state()
        self.previous: HvacState | None = None
        self._pending: HvacState = self.state
        self._lock = asyncio.Lock()
        self._closed = False
        self._save_task: asyncio.Task | None = None
        self._listeners: list[Callable[[], None]] = []
        self._store = unit_store(hass, unit_id)

    def _default_state(self) -> HvacState:
        caps = self.capabilities
        return self.device.normalise(
            HvacState(False, caps.modes[0], caps.temperature.snap(DEFAULT_SETPOINT))
        )

    def _restore(self, data) -> HvacState | None:
        if not isinstance(data, dict):
            return None
        try:
            return self.device.normalise(state_from_dict(data))
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Discarding stored state %s: %s", data, err)
            return None

    async def async_load(self) -> None:
        """Restore state and previous from storage."""
        data = await self._store.async_load() or {}
        self.state = self._restore(data.get("state")) or self._default_state()
        self.previous = self._restore(data.get("previous"))
        self._pending = self.state

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "state": state_to_dict(self.state),
                "previous": (
                    None if self.previous is None else state_to_dict(self.previous)
                ),
            }
        )

    @callback
    def add_listener(self, cb: Callable[[], None]) -> CALLBACK_TYPE:
        """Call ``cb`` whenever state changes; returns the remover."""
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    async def async_set(self, *, context: Context | None = None, **changes) -> None:
        """Apply ``changes`` (HvacState fields; ``features`` merges).

        While the unit is off and stays off, the change is stored, not sent.
        Otherwise it is sent; state and previous move only after a
        successful send. Calls that arrive during a send coalesce: the
        newest state is sent once the current send is done.
        """
        features = changes.pop("features", None)
        pending = replace(self._pending, **changes)
        if features is not None:
            pending = replace(pending, features={**pending.features, **features})
        self._pending = self.device.normalise(pending)
        async with self._lock:
            self._raise_if_closed()
            target = self._pending
            if target == self.state:
                return
            if not target.power and not self.state.power:
                self.state = target
                await self._async_save()
                self._notify()
                return
            await self._async_send(target, (), context)

    async def async_action(self, name: str, *, context: Context | None = None) -> None:
        """Send the one-shot action ``name`` with the current state."""
        async with self._lock:
            self._raise_if_closed()
            await self._async_send(self.state, (name,), context)

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise HomeAssistantError("IR HVAC is reloading; try again")

    async def async_shutdown(self) -> None:
        """Before a reload/unload: finish the send and save in progress, then
        refuse new ones, so the next instance loads what was really sent."""
        self._closed = True
        async with self._lock:
            pass
        if self._save_task is not None:
            await self._save_task

    async def _async_send(self, target, actions, context) -> None:
        command = self.device.encode(self.previous, target, actions)
        try:
            await async_send_signal(self.hass, self.emitter, command.signal, context)
        except Exception as err:
            # A change queued during this send was built on this one and
            # still carries it: the newest wish is sent, as the caller of
            # that change expects.
            if self._pending is target:  # nothing newer queued: drop the change
                self._pending = self.state
            if isinstance(err, HomeAssistantError):
                raise
            raise HomeAssistantError(f"{self.emitter} could not send: {err}") from err
        self.previous = self.state = command.state
        if self._pending is target:  # keep changes queued during the send
            self._pending = command.state
        await self._async_save()
        self._notify()

    def power_reported(self, on: bool) -> None:
        """The power sensor saw the unit turn on/off: follow, send nothing."""
        if self.state.power == on:
            return
        self.state = self._pending = replace(self.state, power=on)
        if self.previous is not None:
            self.previous = replace(self.previous, power=on)
        self._save_task = self.hass.async_create_task(self._async_save())
        self._notify()
