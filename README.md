
![Auto Arm](assets/images/autoarm-dark-256x256.png){ align=left }


# Alarm Auto Arming

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

![py3.14](https://img.shields.io/badge/Python-3.14-blue)
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
Control Panel Integrations][], with additional support for calendar integration, occupancy-driven arming and disarming, manual override via remote control buttons, and mobile push actionable notifications.

Calendar, occupancy, physical buttons, diurnal and bedtime scheduling available with **zero YAML**, support for 11 languages, and everything configured from the Home Assistant settings. Advanced configuration for transition logic, and fine-tuning for notifications and other scheduling, available from optional YAML configuration.

Full documentation is at [autoarm.rhizomatics.org.uk](https://autoarm.rhizomatics.org.uk), and for AI assistants as [llms.txt](https://autoarm.rhizomatics.org.uk/llms.txt) or, all in one, [llms-full.txt](https://autoarm.rhizomatics.org.uk/llms-full.txt).

!!! question inline end "Why use alarm control panels?"
    A (virtual) [Manual Control Panel](https://www.home-assistant.io/integrations/manual/) is useful, even if there is no real alarm system, as a **single central state of the home**, and then use that to drive automations, notifications etc rather than littering notifications with checks for presence, time of day, vacations or similar.

    For example, it is likely that many things will change if `ARMED_VACATION` applies, and you may want to have all PIR alerts silenced if alarm state is `DISARMED`. This builds on how real alarm systems have worked for decades.

    One big obstacle to using Alarm Control Panel is having to remember to change the alarm panel state when people are in or out of the house, at night or when away on holiday.
    *Auto Arm* solves that problem, and makes the Alarm Control Panel essential for any well-automated home.

## Setup

The [Quick Start](./quick_start.md) will get you working quickly.

!!! note "Migrating from YAML-only"
    Existing YAML configurations are automatically migrated to a config entry on restart. See [Migration Guide](configuration/migration.md) for details.

## How it Works

These are the checks and decisions controlling arming:

- **Diurnal**
  - Is it day time or night time?
- **Occupancy**
  - Is everybody home?
- **Bedtime**
  - Is it time for bed and people asleep?
- **Plans**
  - Is there a vacation in the calendar?
- **Interventions**
  - Has someone hit a physical 'disarm' button?
  - Is there a real alarm panel that has changed state?

See [Automated Arming](automated_arming.md) for the various mechanisms, options and how to configure.

## Home Assistant Features Supported

- [Alarm Control Panel Integrations][]
- [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Button Integration][]
- [Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
- [Conditions][] - the entire rules engine runs on these
- [Conversation](https://www.home-assistant.io/integrations/conversation/)
- [Device Tracker Integration](https://www.home-assistant.io/integrations/device_tracker/) - Used to determine presence for home occupancy
- [Notifications](https://www.home-assistant.io/integrations/notify/) - Additional support for [Supernofify](https://supernotify.rhizomatics.org.uk/latest/)
- [Person Integration][]
- [Repairs](https://www.home-assistant.io/integrations/repairs/)
    - Raises repairs for invalid transition configurations
- [Sun Integration](https://www.home-assistant.io/integrations/sun/)
- [Times of the Day](https://www.home-assistant.io/integrations/tod/)
- [Tools](https://www.home-assistant.io/docs/tools/dev-tools/)
    - Configurable integration with UI config flow and options
    - Reloadable from the *YAML* tab
    - Exposes *entities* for its configuration and last calendar event.
- [Voice Control](https://www.home-assistant.io/voice_control/)




## References

* [Home Assistant Calendar Integration](https://www.home-assistant.io/integrations/calendar/)
* [Home Assistant Manual Control Panel docs](https://www.home-assistant.io/integrations/manual/) for more info.
* Handy [Dashboard Alarm Panel](https://www.home-assistant.io/dashboards/alarm-panel/) widget to add to your Home Assistant dashboard.

##  Rhizomatics Open Source for Home Assistant

### HACS
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - OpenTelemetry (OTLP) and Syslog event capture for Home Assistant. Zero YAML install.
- [Supernotify](https://supernotify.rhizomatics.org.uk) - Unified notification for easy multi-channel messaging, including powerful chime and security camera integration. Zero YAML install.


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integrate with ANPR/ALPR licence plate cameras via file system (NAS/FTP) to MQTT with optional image analysis and UK DVLA integration.
- [HomeAssistant REPL](https://homeassistant-repl.rhizomatics.org.uk) - Python REPL for Home Assistant development and data exploration
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatically notify via MQTT on Docker image updates, with advanced handling to extract versions and release notes from images, and option to remotely pull and restart containers from Home Assistant. Also available on [PyPI](https://pypi.org/project/updates2mqtt/)

[![Built with MaterialX for ProperDocs](https://img.shields.io/badge/MaterialX_for_ProperDocs-526CFE?style=for-the-badge&logo=MaterialForMkDocs&logoColor=white)](https://github.com/jaywhj/mkdocs-materialx)


[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
[CalendarEvent]: https://github.com/home-assistant/core/blob/56a71e6798ada65e9c99f92f64bd4168e98b935b/homeassistant/components/calendar/__init__.py#L364
[Alarm Control Panel Integrations]: https://www.home-assistant.io/integrations/?search=alarm+control+panel
[Conditions]: https://www.home-assistant.io/docs/scripts/conditions/
[HACS]: https://hacs.xyz
[Button Integration]: https://www.home-assistant.io/integrations/button/
[Person Integration]: https://www.home-assistant.io/integrations/person/
