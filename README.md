[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Alarm Auto Arming


[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/autoarm)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/autoarm/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/autoarm/main)
[![Github Deploy](https://github.com/rhizomatics/autoarm/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/autoarm/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/autoarm/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/autoarm/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/autoarm/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/autoarm/actions/workflows/dependabot/dependabot-updates)

Automate the arming and disarming of the built-in Home Assistant [Alarm
Control Panel](https://www.home-assistant.io/integrations/alarm_control_panel/), with additional support for calendar integration, manual override via remote control buttons, and mobile push actionable notifications.

!!! question inline end "Why use alarm control panels?"
    A (virtual) [Manual Control Panel](https://www.home-assistant.io/integrations/manual/) is useful,
    even if there is no real alarm system, as a single central place to hold the **overall state of
    the home**, and then use that to drive automations, notifications etc

    For example, it is likely that many things will change if `ARMED_VACATION` applies, and
    you may want to have all PIR alerts silenced if alarm state is `DISARMED`. This builds
    on how real alarm systems have worked for decades.

    One big obstacle to using Alarm Control Panel is having to remember to change the
    alarm panel state when people are in or out of the house, at night or when away on holiday.
    *AutoArm* solves that problem, and makes the Alarm Control Panel essential for any
    well-automated home.

## Setup

Register this GitHub repo as a custom repo in your [HACS]( https://hacs.xyz) configuration.

Notifications will work with any HomeAssistant notification implementation, and works best with [Supernotifier](https://supernotify.rhizomatics.org.uk) for multi-channel notifications with mobile actions.

## Automated Arming

Arming has 4 complementary modes of operation:

### Button Integration

Handy if you have a Zigbee, 433Mhz or similar button panel by the door - choose a button
for `DISARMED`,`ARMED_AWAY` etc, or a *Reset* button to set the panel by the default algorithm.

### Mobile Action

This works similar to the buttons, except its driven by [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/). See [Mobile Actions](mobile_actions.md)
for more information.

### Calendar Integration

Use a Home Assistant [calendar integration](https://www.home-assistant.io/integrations/?cat=calendar) to
define when and how to arm the control panel. If you don't have one, follow these [instructions](configuration/create_calendar.md).

This can be an entry for that purpose, for example a recurring entry on a [Local Calendar](https://www.home-assistant.io/integrations/local_calendar/) dedicated to AutoArm, or looking up an existing calendar to find vacations by pattern.

Using a [Remote Calendar](https://www.home-assistant.io/integrations/remote_calendar/), [Google Calendar](https://www.home-assistant.io/integrations/google/) or similar also means that alarm scheduling
can be done remotely, even if you have no remote access to Home Assistant.

Multiple calendars, of different types, can be configured, and specific alarm states / match patterns per calendar. See the [example configuration](configuration/examples/typical.md)

If there's no calendar event live, then arming state can fall back to the Sun and Occupancy Automation,
or fixed at a default state, or left to manual control.

### Default Algorithm - Sun and Occupancy

Arming can happen strictly by sunset and sunrise, and by occupancy.

| Diurnal State | Occupancy State | Alarm State    |
| ------------- | --------------- | -------------- |
| day           | occupied        | ARMED_HOME(*)  |
| day           | empty           | ARMED_AWAY     |
| night         | occupied        | ARMED_NIGHT    |
| night         | occupied        | ARMED_AWAY     |

(*) This can be overridden using `occupied_daytime_state` in the configuration, for example
if you prefer to have the alarm set to `disarmed` when people are home and its daylight.

Two other states, `ARMED_VACATION` and `DISARMED` can be set manually, by buttons, or calendar.

If you need more predictability, especially for high latitudes where sunrise varies wildly through the year,
set up a calendar and define exactly when you want disarming or arming to happen.

Similarly, there's a `sunrise_cutoff` option to prevent alarm being armed at
4am if you live far North, like Norway or Scotland.

## Throttling

To guard against loops, or other reasons why arming might be triggered too often,
rate limiting is applied around the arm call, limited to a set number of calls within
the past so many seconds.


## Alarm Panel Configuration

Autoarm will work with any Home Assistant [Alarm Control Panel](https://www.home-assistant.io/integrations/alarm_control_panel/) based integration.

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

## Notifications

Two notifications are sent:

- Alarm status has changed, by any means
- A button has been pressed, and the arm status will be actioned with a few seconds delay

The alarm status message uses the `quiet` profile, and the other one `normal` profile. This
lets you change the priority, or any of the other message content.

```yaml
notify:
    common:
      service: notify.supernotify
    quiet:
      data:
        priority: low
    normal:
      data:
        priority: medium
```

For more notification flexibility, try [Supernotify](https://supernotify.rhizomatics.org.uk)

## Home Assistant features

- The component is reloadable from the *Developer Tools* page
- Autoarm exposes *entities* for its configuration and last calendar event.

## References

* [Home Assistant Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
* [Home Assistant Manual Control Panel docs](https://www.home-assistant.io/integrations/manual/) for more info.
* Handy [Dashboard Alarm Panel](https://www.home-assistant.io/dashboards/alarm-panel/) widget to add to your Home Assistant dashboard.
