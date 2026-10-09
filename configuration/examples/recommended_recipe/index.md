# Recommended Recipe

Source: https://autoarm.rhizomatics.org.uk/configuration/examples/recommended_recipe/

A simple standard setup for a home that's lived in most days, with no YAML:

- **Armed night** for a fixed bedtime every day, from a [Time of Day](https://www.home-assistant.io/integrations/tod/) sensor
- **Armed home** from sunset until bedtime, when sunset comes first
- **Disarmed** when bedtime ends, whether or not the sun is up yet
- **Armed away** whenever everyone is out
- A calendar for vacations and other planned time away, with no need to switch the bedtime sensor off for them

## Set Up

1. Create a **Bedtime** sensor in **Settings** > **Devices & Services** > **Helpers** > **Create Helper** > **Times of the Day**, on at 23:00 and off at 07:00, or whatever suits.
1. Have a calendar for vacations and time away. If you don't have one, see [Create a Calendar](https://autoarm.rhizomatics.org.uk/configuration/create_calendar/index.md).
1. Add the integration from **Settings** > **Devices & Services** > **Add Integration**, searching for **Auto Arm**, or if it's already set up, open **Settings** > **Devices & Services** > **Auto Arm** > **Configure**:

| Setting                                   | Value                                                 |
| ----------------------------------------- | ----------------------------------------------------- |
| **Bedtime sensor for Armed Night**        | The Bedtime sensor                                    |
| **Calendars for vacations and time away** | The calendar                                          |
| **People for occupancy based arming**     | Everyone who lives in, already chosen on a new set up |

Everything else is left at its default on a new set up.

If Auto Arm was already set up, its existing settings are kept, so also check these in the **Advanced** section:

| Setting                                           | Value      |
| ------------------------------------------------- | ---------- |
| **Default arming state when occupied during day** | Disarmed   |
| **Default arming state when occupied at night**   | Armed Home |

## An Ordinary Day

With someone home, and sunset at 18:00:

| Time  | What happens       | Alarm state   |
| ----- | ------------------ | ------------- |
| 07:00 | Bedtime sensor off | `disarmed`    |
| 18:00 | Sunset             | `armed_home`  |
| 23:00 | Bedtime sensor on  | `armed_night` |

Sunrise makes no difference. In summer it comes during bedtime, and is ignored. In winter it comes after bedtime has ended and the alarm is already disarmed. If sunset comes after bedtime has started, it's ignored too.

If everyone is out, the alarm is `armed_away` at any time of day. Coming home during bedtime sets it to `armed_night`.

## Vacations and Time Away

Add a calendar event with **Vacation** or **Away** in its title. While the event is live it takes priority over the Bedtime sensor, which carries on turning on and off with no effect.

When the event ends during bedtime, the alarm goes to `armed_night`, or stays `armed_away` until someone is home. When it ends at any other time, the alarm is disarmed if someone is home, or armed away if not.

On a day with one of these calendar events, sunset doesn't arm the alarm, since the sunrise and sunset [triggers](https://autoarm.rhizomatics.org.uk/automated_arming/#triggers) are off by default on calendar days. Bedtime still does.
