# Advanced Configuration

!!! note
    Some advanced options remain YAML only, either because they are infrequently needed, or difficult to fit into a standard Home Assistant configuration screen.

### When an Event Ends

The **Advanced** section of the options has separate settings for an **armed** event ending (`armed_home`,
`armed_away`, `armed_night`, `armed_vacation` or `armed_custom_bypass`) and a **disarmed** event ending, unless another event is still live. Each can be:

| Setting                           | Armed event ends                                                                                                      | Disarmed event ends                   |
|-----------------------------------|-----------------------------------------------------------------------------------------------------------------------|---------------------------------------|
| **Auto**, the default             | **By occupancy and sun** if the sunrise or sunset [trigger](automated_arming.md#triggers) is active that day, otherwise **By occupancy** | The same                              |
| **By occupancy and sun**          | Worked out from who's home and whether it's day or night, the same as any other reset                                 | The same                              |
| **By occupancy**                  | Disarms, or arms away if everyone is out                                                                              | Arms home, or away if everyone is out |
| **Manual**                        | Goes back to the state before the event                                                                               | The same                              |
| A fixed state, such as `disarmed` | Goes to that state                                                                                                    | The same                              |

**By occupancy** ignores day and night. That matters when an event ends close to sunrise or sunset:

An `armed_night` event ending at 06:45, before the sun is up, would be worked out as still night by **By occupancy and sun** and stay armed for the night, until sunrise disarms it a few minutes later. With **By occupancy** it disarms as the event ends.

**Auto** only takes day and night into account when sunrise or sunset will re-evaluate the state that day. With the sunrise and sunset triggers left at their default of **Auto**, they're off on any day with a `disarmed`, `armed_home` or `armed_night` calendar event, so an event ending that day goes by occupancy alone. On a day with only `armed_away`, `armed_vacation` or `armed_custom_bypass` events, they stay on, so an event ending after dark arms for the night if someone is home.

In YAML, these are `auto`, `auto_sun` and `auto_occupancy` for `no_event_mode`, `armed_end_mode` and `disarmed_end_mode`.

### Other Resets When Using Calendars

Resets that don't come from an event starting or ending, such as sunrise, someone arriving or leaving, or
the reset button, work out the state like this:

1. While an event is live, a reset button or the `autoarm.reset_state` action returns to the event's state.
   Automatic resets, such as sunrise, leave it alone, along with any manual change made during the event.
2. Otherwise, if an event ended earlier today, the setting for that kind of event ending applies:
   **Manual** leaves the state alone, **Auto (occupancy)** and fixed states reset as they would at the end
   of the event, and **Auto (occupancy and diurnal)** works the state out as usual.
3. With no calendar activity today, the state is worked out as if there were no calendars.

### Notification Coalescing

Calendar changes often arrive in pairs - one event ending right as another begins, or a burst of changes
from re-matching after a calendar update. To avoid a flurry of notifications for what is really one change,
calendar-sourced notifications wait for a grace period (`notify_grace_period` in YAML, default one minute)
before sending. If another calendar-sourced change lands within that window, the wait restarts and only the
net change - from the state before the first change to the state after the last - is notified. If that nets
out to no change at all, nothing is sent.

This only debounces the *notification*; the alarm panel's actual state still updates immediately as each calendar-driven change happens.

## Automated Transitions

!!! note "YAML-only"
    Transition conditions are configured entirely in YAML.

If nothing else is configured ( occupancy, buttons, calendars ) then arming will still happen by the state of the sun. The rules for this, and how occupancy is used, are all defined as Home Assistant [Conditions] and can be overridden as you need.

| Diurnal State | Occupancy State | Alarm State   |
|---------------|-----------------|---------------|
| day           | occupied        | ARMED_HOME(*) |
| day           | empty           | ARMED_AWAY    |
| night         | occupied        | ARMED_NIGHT   |
| night         | occupied        | ARMED_AWAY    |

(*) This can be overridden using `state_default` in the `occupancy` configuration, for example if you prefer to have the alarm set to `disarmed` when people are home and its daylight.

Two other states, `armed_vacation` and `disarmed` can be set manually, by buttons, or calendar.

If you need more predictability, especially for high latitudes where sunrise varies wildly through the year,
set up a calendar and define exactly when you want disarming or arming to happen.

### Algorithm Conditions

The defaults below will be used if there is no transition defined ( you can override just one of them if
you prefer, and the others will remain as default, leave `conditions` empty if you really want to disable
the transition).

```yaml
autoarm:
  transitions:
    armed_home:
        - "{{ autoarm.occupied and not autoarm.night }}"
        - "{{ autoarm.computed and autoarm.occupied_daytime_state == 'armed_home'}}"
    armed_away: "{{ not autoarm.occupied and autoarm.computed}}"
    disarmed:
        - "{{ autoarm.occupied and not autoarm.night }}"
        -  "{{ autoarm.computed and autoarm.occupied_daytime_state == 'disarmed'}}"
    armed_night: "{{ autoarm.occupied and autoarm.night and autoarm.computed}}"
    armed_vacation: "{{ autoarm.vacation }}"
```

Conditions have an `autoarm` field added to the context, with these values. The examples above are all
in the [shortcut template style](https://www.home-assistant.io/docs/scripts/conditions/#template-condition-shorthand-notation), though any other style of `condition` can be used, along with other Jinja2 features and Home Assistant extras, including AND/OR/NOT logic.

| Field                      | Type            | Usage                                                    |
|----------------------------|-----------------|----------------------------------------------------------|
| daytime                    | bool            | The `sun` integration thinks it is daytime               |
| night                      | bool            | The `sun` integration thinks it is nighttime             |
| occupied                   | bool            | If any of the `person` entities have state `home`        |
| at_home                    | list[str]       | List of occupancy entities at home                       |
| not_home                   | list[str]       | List of occupancy entities not at home                   |
| manual                     | bool            | Alarm Panel is in vacation or 'custom bypass' mode       |
| computed                   | bool            | State is being computed by the algorithm                 |
| vacation                   | bool            | Shortcut for Alarm Panel state being ARMED_VACATION      |
| bypass                     | bool            | Shortcut for Alarm Panel state being ARMED_CUSTOM_BYPASS |
| disarmed                   | bool            | Shortcut for Alarm Panel state being DISARMED            |
| state                      | str             | Current alarm control panel state                        |
| calendar_event             | [CalendarEvent] | Most recent active Calendar Event                        |
| calendar_event.start       | datetime        | Event start date/time                                    |
| calendar_event.end         | datetime        | Event end date/time                                      |
| calendar_event.summary     | str             | Event summary                                            |
| calendar_event.description | str             | Event description                                        |
| calendar_event.location    | str             | Event location                                           |
| occupied_daytime_state     | str             | Default state for occupied in day time                   |

[CalendarEvent]: https://github.com/home-assistant/core/blob/56a71e6798ada65e9c99f92f64bd4168e98b935b/homeassistant/components/calendar/__init__.py#L364
[Alarm Control Panel Integrations]: https://www.home-assistant.io/integrations/?search=alarm+control+panel
[Conditions]: https://www.home-assistant.io/docs/scripts/conditions/
[HACS]: https://hacs.xyz
[Button Integration]: https://www.home-assistant.io/integrations/button/
[Person Integration]: https://www.home-assistant.io/integrations/person/
