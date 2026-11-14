# Power sensor

Someone may switch the unit on or off with its remote control. Home
Assistant cannot see infrared commands it did not send, so the climate
entity would show the wrong state. A power sensor fixes that.

Any `binary_sensor` that is `on` while the unit runs will do. When it turns
on while the entity is off, the entity shows the unit on, with the last
settings it had. When it turns off, the entity shows off. No infrared
command is sent in either case: Home Assistant only catches up with what
happened. `unavailable` and `unknown` are ignored.

## Example: a smart plug that measures power

A template binary sensor (Settings > Devices & services > Helpers >
Template > Binary sensor, or in YAML):

```yaml
template:
  - binary_sensor:
      - name: "Living room A/C running"
        state: "{{ states('sensor.living_room_ac_plug_power') | float(0) > 30 }}"
        delay_off:
          minutes: 2
```

Pick a threshold above the unit's standby power. `delay_off` keeps the
sensor on while the compressor cycles.

Then pick this sensor as the unit's power sensor (Configure on the IR HVAC
device).
