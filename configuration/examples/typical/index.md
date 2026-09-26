# Typical Configuration

Source: https://autoarm.rhizomatics.org.uk/configuration/examples/typical/

More extensive example configuration, using most of the features.

## UI vs YAML Settings

With the config flow, some settings are now managed in the UI:

| Setting                                   | Where        | Notes                                                                                                                          |
| ----------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Alarm panel entity                        | UI (setup)   | Selected when adding the integration                                                                                           |
| Change state using panel actions          | UI (options) | On for new installs, see [Create Panel](https://autoarm.rhizomatics.org.uk/configuration/create_panel/index.md)                |
| Arm and explain by voice, Disarm by voice | UI (options) | Voice and chat commands, see [Automated Arming](https://autoarm.rhizomatics.org.uk/automated_arming/#built-in-agent-sentences) |
| Calendar entities                         | UI (options) | Which calendars to use                                                                                                         |
| Person entities                           | UI (options) | Which persons to track for occupancy                                                                                           |
| Occupancy day/night defaults              | UI (options) | Default alarm state when occupied                                                                                              |
| No-event mode                             | UI (options) | Behaviour when no calendar event is active                                                                                     |
| Diurnal                                   | UI (options) | Sunrise/sunset configuration                                                                                                   |
| Per-calendar state patterns               | YAML         | Regex patterns matching calendar events to alarm states                                                                        |
| Per-calendar poll interval                | YAML         | How often to check each calendar                                                                                               |
| Transitions                               | YAML         | Condition templates for state transitions                                                                                      |
| Buttons                                   | YAML         | Physical button entity mappings                                                                                                |
| Notifications                             | UI (options) | Notification service and targets                                                                                               |
| Notification Profiles                     | YAML         | Notification profile configuration                                                                                             |
| Rate limit                                | YAML         | Throttling for arm calls                                                                                                       |

## Full YAML Example

```yaml
autoarm:
  # YAML: delay_time remains YAML-only
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
  # UI: calendar entities and no_event_mode are configurable via Options
  # YAML: per-calendar state_patterns and poll_interval remain here
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

  # YAML-only: button configuration
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

  # YAML-only: rate limiting
  rate_limit:
    max_calls: 5
    period: 60

  # YAML-only: notification configuration
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
