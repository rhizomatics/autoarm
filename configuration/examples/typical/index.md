# Typical Configuration

Source: https://autoarm.rhizomatics.org.uk/configuration/examples/typical/

More extensive example configuration, using most of the features.

## UI vs YAML Settings

With the config flow, most settings are now managed in the UI:

| Setting                                   | Where                                                     | Notes                                                                                                                                                      |
| ----------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alarm panel entity                        | UI (setup)                                                | Selected when adding the integration                                                                                                                       |
| Change state using panel actions          | UI (options, Advanced)                                    | On for new installs, see [Create Panel](https://autoarm.rhizomatics.org.uk/configuration/create_panel/index.md)                                            |
| Arm and explain by voice, Disarm by voice | UI (options)                                              | Voice and chat commands, see [Automated Arming](https://autoarm.rhizomatics.org.uk/automated_arming/#built-in-agent-sentences)                             |
| Bedtime sensor                            | UI (setup, options)                                       | Times of the Day sensor for `armed_night`, see [Recommended Recipe](https://autoarm.rhizomatics.org.uk/configuration/examples/recommended_recipe/index.md) |
| Calendar entities                         | UI (setup, options)                                       | Which calendars to use                                                                                                                                     |
| Person entities                           | UI (setup, options)                                       | Which persons to track for occupancy                                                                                                                       |
| Occupied states                           | UI (options, Advanced - Diurnal)                          | Alarm state when occupied by day, after bedtime and before bedtime                                                                                         |
| Times of the Day sensors                  | UI (options)                                              | Sensors that set any other alarm state while on                                                                                                            |
| Calendar end modes                        | UI (options, Advanced - Calendar)                         | What happens when an armed or disarmed calendar event ends                                                                                                 |
| Triggers                                  | UI (options, Advanced - Diurnal and Advanced - Occupancy) | Whether sunrise, sunset and people arriving or leaving re-evaluate the state                                                                               |
| Sunrise and sunset                        | UI (options)                                              | Earliest and latest times                                                                                                                                  |
| Calendar match rules                      | UI (options, Advanced - Calendar)                         | Regex patterns matching calendar events to alarm states, copied from YAML if already there                                                                 |
| Calendar poll interval                    | UI (options, Advanced - Calendar)                         | How often to check the calendars                                                                                                                           |
| Transitions                               | YAML                                                      | Condition templates for state transitions                                                                                                                  |
| Buttons                                   | UI (options, Buttons)                                     | Physical button entities and delays, copied from YAML if already there                                                                                     |
| Notifications                             | UI (options)                                              | Notification service and targets, and priorities for Supernotify                                                                                           |
| Notification Profiles                     | YAML                                                      | **Deprecated**, replaced by deeper Supernotify integration in the options, and will be removed when Home Assistant 2027.4 is released                      |
| Rate limit                                | YAML                                                      | Throttling for arm calls                                                                                                                                   |

## Full YAML Example

```yaml
autoarm:
  # MIGRATED delay_time is copied into the Options the first time, and set there from then on
  occupancy:
    delay_time:
      not_home: 180
      home: 0 # the default
  # YAML-only: transition conditions
  transitions:
    armed_home:
      alias: Home with alarm active, such as home alone
      conditions:
        - "{{ autoarm.occupied and not autoarm.night }}"
        - "{{ autoarm.computed and autoarm.occupied_daytime_state == 'armed_home'}}"
    armed_away:
      conditions: "{{ not autoarm.occupied and autoarm.computed}}"
    disarmed:
      conditions:
       - "{{ autoarm.occupied and not autoarm.night }}"
       - "{{ autoarm.computed and autoarm.occupied_daytime_state == 'disarmed'}}"
    armed_night:
      conditions: "{{ autoarm.occupied and autoarm.night and autoarm.computed }}"
    pending:
      conditions:
  # UI: calendar entities and calendar end modes are configurable via Options
  # state_patterns and poll_interval are copied into the Options the first time, and set there from then on
  calendar_control:
    calendars:
      - entity_id: calendar.alarm_control
        alias: Local Calendar only used for autoarm
        poll_interval: 60
        state_patterns:
          disarmed:
            - Disarmed
      - entity_id: calendar.family_events
        poll_interval: 300
        state_patterns:
          armed_vacation:
            - Holiday.*
            - Camping Trip.*
          armed_away:
            - Working at Office

  # MIGRATED buttons are copied into the UI options on first start, and can then be removed from here
  buttons:
    reset:
      entity_id: binary_sensor.button_right
    armed_away:
      delay_time: 180
      entity_id:
        - binary_sensor.button_right
        - binary_sensor.back_door_away
    disarmed:
      entity_id: binary_sensor.button_middle

  # MIGRATED copied into the Options the first time, and set there from then on
  rate_limit:
    max_calls: 5
    period: 60

  # DEPRECATED replaced by deeper Supernotify integration, set up in the Notifications section of the Options,
  # and will be removed when Home Assistant 2027.4 is released
  notify:
    common:
      data:
        actions:
          - action: ALARM_PANEL_DISARM
            title: Disarm Alarm Panel
            icon: sfsymbols:bell.slash
          - action: ALARM_PANEL_RESET
            title: Reset Alarm Panel
            icon: sfsymbols:bell
          - action: ALARM_PANEL_AWAY
            title: Arm Alarm Panel for Going Away
            icon: sfsymbols:airplane
    quiet:
      scenario: alarm_panel_quiet
      data:
        priority: low
    normal:
      scenario: alarm_panel
      source:
        - calendar
      state:
        - armed_away
        - armed_vacation
      data:
        priority: medium
```
