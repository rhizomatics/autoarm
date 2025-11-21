[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Alarm Auto Arming

Automate the arming and disarming of the built-in Home Assistant alarm
control panel, with additional support for manual override via remote
control buttons, and mobile push actionable notifications.

## Setup

Register this GitHub repo as a custom repo
in your [HACS]( https://hacs.xyz) configuration.

Notifications will work with any HomeAssistant notification implementation
but works best with [Supernotifier](https://supernotify.rhizomatics.org.uk) for multi-channel notifications with mobile actions.

## Diurnal settings

Arming can happen strictly by sunset and sunrise.
Alternatively, a defined `sleep_start` and `sleep_end` can be specified, so there's more
predictability, especially for high latitudes where sunrise varies wildly through the year.

Similarly, there's a `sunrise_cutoff` option to prevent alarm being armed at
4am if you live far North, like Norway or Scotland.

## Throttling

To guard against loops, or other reasons why arming might be triggered too often,
rate limiting is applied around the arm call, limited to a set number of calls within
the past so many seconds.

## Example Configuration

Configure in the Home Assistant config, either as a block in a config file, or as a file
of its own using an ``include``.

```yaml
autoarm:
    alarm_panel: alarm_panel.testing
    auto_arm: True
    sleep_start: "09:00:00"
    sleep_end: "22:00:00"
    sunrise_cutoff: "06:30:00"
    arm_away_delay: 180
    reset_button: binary_sensor.button_left
    away_button: binary_sensor.button_right
    disarm_button: binary_sensor.button_middle
    throttle_seconds: 30
    throttle_calls: 6
    occupants:
        - person.house_owner
        - person.tenant
    notify:
        common:
            service: notify.supernotifier
            data:
                actions:
                    action_groups: alarm_panel
                    action_category: alarm_panel
        quiet:
            data:
                priority: low
        normal:
            data:
                priority: medium
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

```
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

## Alarm Panel Configuration

Autoarm will work with any Home Assistant [Alarm Control Panel](https://www.home-assistant.io/integrations/alarm_control_panel/) based integration, whether with a physical panel, virtual, virtual with generic switches for some modes, or entirely automated.

If you don't already have an alarm panel, set up a default manual as below, which creates the
state machine for armed/disarmed status. This is all you need in the way of alarm support for AutoArm to function. You can also choose whether a PIN code is needed or not to arm or disarm.

```yml
alarm_control_panel:
  - platform: manual
    name: Home Alarm Control
    code_arm_required: false
    arming_time: 0
    delay_time: 0
    disarm_after_trigger: false
    trigger_time: 0
```

See [Home Assistant Manual Control Panel docs](https://www.home-assistant.io/integrations/manual/) for more info.

There's also a handy [Dashboard Alarm Panel](https://www.home-assistant.io/dashboards/alarm-panel/) widget to add to your Home Assistant dashboard.
