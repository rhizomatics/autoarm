# Alarm Auto Arming

Source: https://autoarm.rhizomatics.org.uk/

Automate the arming and disarming of the built-in Home Assistant [Alarm Control Panel Integrations](https://www.home-assistant.io/integrations/?search=alarm+control+panel), with additional support for calendar integration, occupancy-driven arming and disarming, manual override via remote control buttons, and mobile push actionable notifications.

Calendar, occupancy and diurnal scheduling available with **zero YAML**, support for 11 languages, and everything configured from the Home Assistant settings. Advanced configuration for physical buttons, and fine-tuning for other scheduling, available from optional YAML configuration.

Why use alarm control panels?

A (virtual) [Manual Control Panel](https://www.home-assistant.io/integrations/manual/) is useful, even if there is no real alarm system, as a **single central state of the home**, and then use that to drive automations, notifications etc rather than littering notifications with checks for presence, time of day, vacations or similar.

For example, it is likely that many things will change if `ARMED_VACATION` applies, and you may want to have all PIR alerts silenced if alarm state is `DISARMED`. This builds on how real alarm systems have worked for decades.

One big obstacle to using Alarm Control Panel is having to remember to change the alarm panel state when people are in or out of the house, at night or when away on holiday. *Auto Arm* solves that problem, and makes the Alarm Control Panel essential for any well-automated home.

## Setup

Auto Arm is one of the default repositories on [HACS](https://hacs.xyz), so there's no need to register a custom repo.

Notifications will work with any HomeAssistant notification implementation, with additional support for [Supernotify](https://supernotify.rhizomatics.org.uk) for multi-channel notifications with mobile actions.

## Configuration

Auto Arm is set up using the Home Assistant Integrations page, with additional advanced configuration available via YAML.

### UI Setup

1. Go to **Settings** > **Devices & Services** > **Add Integration** and search for **Auto Arm**.
1. Select your **Alarm Control Panel** entity (any [Alarm Control Panel Integration](https://www.home-assistant.io/integrations/?search=alarm+control+panel) will work). If you don't have one, see [Create an Alarm Panel](https://autoarm.rhizomatics.org.uk/configuration/create_panel/index.md).
1. Optionally select **Calendar** and **Person** entities.
1. Adjust defaults in **Options** at any time (calendar entities, person entities, occupancy defaults, no-event mode).

### YAML for Advanced Features

Transitions, buttons, notifications, diurnal settings, rate limiting, and per-calendar overrides (state patterns, poll intervals) are configured in YAML. See [Typical Configuration](https://autoarm.rhizomatics.org.uk/configuration/examples/typical/index.md) for a full example.

Migrating from YAML-only

Existing YAML configurations are automatically migrated to a config entry on restart. See [Migration Guide](https://autoarm.rhizomatics.org.uk/configuration/migration/index.md) for details.

## Automated Arming

See [Automated Arming](https://autoarm.rhizomatics.org.uk/automated_arming/index.md) for the various mechanisms, options and how to configure.

The full list of how alarm panel state can be set:

| Source        | Description                                                               |
| ------------- | ------------------------------------------------------------------------- |
| calendar      | Calendar events (with optional override for selected events by occupancy) |
| mobile        | Mobile action                                                             |
| occupancy     | Occupancy calculation, e.g. automatically switching off `ARMED_AWAY`      |
| alarm_panel   | Changes made to Alarm Control Panel outside of Auto Arm                   |
| button        | A physical button push                                                    |
| action        | A Home Assistant Action call (previously known as 'Service')              |
| sunrise       | HomeAssistant `sun` integration event                                     |
| sunset        | HomeAssistant `sun` integration event                                     |
| startup       | Alarm changes made as part of Auto Arm startup                            |
| zombification | Home Assistant alarm panel got itself into a 'zombie' state and was reset |

## Throttling

To guard against loops, or other reasons why arming might be triggered too often, rate limiting is applied around the arm call, limited to a set number of calls within the past so many seconds. Configured by `rate_limit` section in config.

## Notifications

Notifications is set up via the integration settings.

Two notifications are sent:

- Alarm status has changed, by any means
- A button has been pressed, and the arm status will be actioned with a few seconds delay

If [Supernotify](https://supernotify.rhizomatics.org.uk) is installed, its `supernotify.notify` action is offered first in the **Notification Action** list. It takes the same fields as the YAML `data` section, such as `priority`, and adds the [Mobile Actions](https://autoarm.rhizomatics.org.uk/mobile_actions/index.md) to disarm, reset or arm away from the notification. Leave the targets blank to let Supernotify choose who to notify. The action chosen here is used for every notification, unless a YAML profile sets its own `service`.

### Advanced Notifications

More control over notifications is available using YAML configuration,

The alarm status message by default uses a `quiet` profile, and another one called `normal`, which can be overridden with as many profiles named as you like. Each profile is defined by the source of alarm change, optionally restricted by which alarm states are involved, and lets you change the priority, or any of the other message content (the ubiquitous Home Assistant `data` section).

```yaml
notify:
    quiet:
      scenario: nerdy
      data:
        priority: low
    normal:
      source:
        - calendar
      state:
        - armed_vacation
        - armed_away
      data:
        priority: medium
```

If you want to send to e-mail and mobile then this will fail with a notify group unless you use very basic messages, since additional fields, like the `actions` in the `data` field for Actionable Notifications aren't supported by other notification platforms. The best way to resolve that is with [Supernotify](https://supernotify.rhizomatics.org.uk) which will tune each message for the underlying transport ( mobile apps, and also e-mail, text, chime etc.) along with lots of other tuning options and automatic discovery.

## Home Assistant Features Supported

- [Alarm Control Panel Integrations](https://www.home-assistant.io/integrations/?search=alarm+control+panel)
- [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Button Integration](https://www.home-assistant.io/integrations/button/)
- [Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
- [Conditions](https://www.home-assistant.io/docs/scripts/conditions/)
- [Conversation](https://www.home-assistant.io/integrations/conversation/)
- [Device Tracker Integration](https://www.home-assistant.io/integrations/device_tracker/)
- [Notifications](https://www.home-assistant.io/integrations/notify/)
- [Person Integration](https://www.home-assistant.io/integrations/person/)
- [Repairs](https://www.home-assistant.io/integrations/repairs/)
  - Raises repairs for invalid transition configurations
- [Sun Integration](https://www.home-assistant.io/integrations/sun/)
- [Tools](https://www.home-assistant.io/docs/tools/dev-tools/)
  - Configurable integration with UI config flow and options
  - Reloadable from the *YAML* tab
  - Exposes *entities* for its configuration and last calendar event.
- [Voice Control](https://www.home-assistant.io/voice_control/)

## References

- [Home Assistant Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
- [Home Assistant Manual Control Panel docs](https://www.home-assistant.io/integrations/manual/) for more info.
- Handy [Dashboard Alarm Panel](https://www.home-assistant.io/dashboards/alarm-panel/) widget to add to your Home Assistant dashboard.

## Rhizomatics Open Source for Home Assistant

### HACS

- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - OpenTelemetry (OTLP) and Syslog event capture for Home Assistant. Zero YAML install.
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Unified notification for easy multi-channel messaging, including powerful chime and security camera integration. Zero YAML install.

### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integrate with ANPR/ALPR licence plate cameras via file system (NAS/FTP) to MQTT with optional image analysis and UK DVLA integration.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatically notify via MQTT on Docker image updates, with advanced handling to extract versions and release notes from images, and option to remotely pull and restart containers from Home Assistant. Also available on [PyPI](https://pypi.org/project/updates2mqtt/)
