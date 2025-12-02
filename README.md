
![AutoArm](assets/images/autoarm-dark-256x256.png){ align=left }


# Alarm Auto Arming

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/autoarm)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/autoarm/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/autoarm/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/autoarm/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/autoarm/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/autoarm/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/autoarm/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/autoarm/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/autoarm/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/autoarm/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/autoarm/actions/workflows/dependabot/dependabot-updates)

<br/>
<br/>
<br/>


Automate the arming and disarming of the built-in Home Assistant [Alarm
Control Panel Integrations][], with additional support for calendar integration, manual override via remote control buttons, and mobile push actionable notifications.

!!! question inline end "Why use alarm control panels?"
    A (virtual) [Manual Control Panel](https://www.home-assistant.io/integrations/manual/) is useful, even if there is no real alarm system, as a **single central state of the home**, and then use that to drive automations, notifications etc rather than littering notifications with checks for presence, time of day, vacations or similar.

    For example, it is likely that many things will change if `ARMED_VACATION` applies, and you may want to have all PIR alerts silenced if alarm state is `DISARMED`. This builds on how real alarm systems have worked for decades.

    One big obstacle to using Alarm Control Panel is having to remember to change the
    alarm panel state when people are in or out of the house, at night or when away on holiday.
    *AutoArm* solves that problem, and makes the Alarm Control Panel essential for any
    well-automated home.

## Setup

Register this GitHub repo as a custom repo in your [HACS][] configuration.

Notifications will work with any HomeAssistant notification implementation, and works best with [Supernotify](https://supernotify.rhizomatics.org.uk) for multi-channel notifications with mobile actions.

## Alarm Panel Configuration

Autoarm will work with any Home Assistant of the [Alarm Control Panel Integrations][]. If you don't have one, try
[Create an Alarm Panel](configuration/create_panel.md)

## Automated Arming

See [Automated Arming](automated_arming.md) for the various mechanisms, options and how to configure.

## Throttling

To guard against loops, or other reasons why arming might be triggered too often,
rate limiting is applied around the arm call, limited to a set number of calls within
the past so many seconds. Configured by `rate_limit` section in config.


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
        apply-scenarions: nerdy
    normal:
      data:
        priority: medium
```

 If you want to send to e-mail and mobile then this will fail with a notify group unless you
 use very basic messages, since additional fields, like the `actions` in the `data` field for
 Actionable Notifications aren't supported by other notification platforms. The
 best way to resolve that is with [Supernotify](https://supernotify.rhizomatics.org.uk) which will
 tune each message for the underlying transport ( mobile apps, and also e-mail, text, chime etc.)
 along with lots of other tuning options.

## Home Assistant Features Supported

- [Alarm Control Panel Integrations][]
- [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
- [Sun Integration](https://www.home-assistant.io/integrations/sun/)
- [Person Integration][]
- [Button Integration][]
- [Device Tracker Integration](https://www.home-assistant.io/integrations/device_tracker/)
- [Conditions][]
- [Notifications](https://www.home-assistant.io/integrations/notify/)
- [Repairs](https://www.home-assistant.io/integrations/repairs/)
    - Raises repairs for invalid transition configurations
- [Developer Tools](https://www.home-assistant.io/docs/tools/dev-tools/)
    - Reloadable from the *YAML* tab
    - Exposes *entities* for its configuration and last calendar event.

## References

* [Home Assistant Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
* [Home Assistant Manual Control Panel docs](https://www.home-assistant.io/integrations/manual/) for more info.
* Handy [Dashboard Alarm Panel](https://www.home-assistant.io/dashboards/alarm-panel/) widget to add to your Home Assistant dashboard.

[![Built with Material for MkDocs](https://img.shields.io/badge/Material_for_MkDocs-526CFE?style=for-the-badge&logo=MaterialForMkDocs&logoColor=white)](https://squidfunk.github.io/mkdocs-material/)

[CalendarEvent]: https://github.com/home-assistant/core/blob/56a71e6798ada65e9c99f92f64bd4168e98b935b/homeassistant/components/calendar/__init__.py#L364
[Alarm Control Panel Integrations]: https://www.home-assistant.io/integrations/?search=alarm+control+panel
[Conditions]: https://www.home-assistant.io/docs/scripts/conditions/
[HACS]: https://hacs.xyz
[Button Integration]: https://www.home-assistant.io/integrations/button/
[Person Integration]: https://www.home-assistant.io/integrations/person/
