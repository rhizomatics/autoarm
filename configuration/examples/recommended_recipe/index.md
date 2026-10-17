# Recommended Recipe

Source: https://autoarm.rhizomatics.org.uk/configuration/examples/recommended_recipe/

A simple standard setup for a home that's lived in most days, with no YAML:

- **Armed night** for a fixed bedtime every day, from a [Times of the Day](https://www.home-assistant.io/integrations/tod/) sensor
- **Armed home** from sunset until bedtime, when sunset comes first
- **Disarmed** when bedtime ends, or **armed home** until sunrise if it's still dark
- **Armed away** whenever everyone is out
- A calendar for vacations and other planned time away, with no need to switch the bedtime sensor off for them
- Coming home on the last day of a vacation or time away ends it, without waiting for the calendar

## Set Up

1. Create a **Bedtime** sensor in **Settings** > **Devices & Services** > **Helpers** > **Create Helper** > **Times of the Day**, on at 23:00 and off at 07:00, or whatever suits.
1. Have a calendar for vacations and time away. If you don't have one, see [Create a Calendar](https://autoarm.rhizomatics.org.uk/configuration/create_calendar/index.md).
1. Add the integration from **Settings** > **Devices & Services** > **Add Integration**, searching for **Auto Arm**, or if it's already set up, open **Settings** > **Devices & Services** > **Auto Arm** > **Configure**:

| Setting                                          | Value                                                 |
| ------------------------------------------------ | ----------------------------------------------------- |
| **Bedtime - Times of the Day Sensor**            | The Bedtime sensor                                    |
| **Occupancy - Calendars**                        | The calendar                                          |
| **Presence - People for Occupancy Based Arming** | Everyone who lives in, already chosen on a new set up |

Everything else is left at its default on a new set up.

If Auto Arm was already set up, its existing settings are kept, so also check these in the **Advanced - Diurnal** section:

| Setting                                        | Value      |
| ---------------------------------------------- | ---------- |
| **Occupied state between morning and evening** | Disarmed   |
| **Occupied state between bedtime and morning** | Armed Home |
| **Occupied state between evening and bedtime** | Armed Home |

## An Ordinary Day

With someone home, and sunset at 18:00:

| Time  | What happens       | Alarm state                                             |
| ----- | ------------------ | ------------------------------------------------------- |
| 07:00 | Bedtime sensor off | `disarmed`, or `armed_home` until sunrise if still dark |
| 18:00 | Sunset             | `armed_home`                                            |
| 23:00 | Bedtime sensor on  | `armed_night`                                           |

In summer, sunrise comes during bedtime and is ignored. In winter, bedtime ends before sunrise, so the alarm goes to `armed_home` at 07:00 and is disarmed at sunrise. To disarm as bedtime ends whatever the sun is doing, set **Occupied state between bedtime and morning** to Disarmed. If sunset comes after bedtime has started, it's ignored too.

If everyone is out, the alarm is `armed_away` at any time of day. Coming home during bedtime sets it to `armed_night`.

## Vacations and Time Away

Add a calendar event with **Vacation** or **Away** in its title. While the event is live it takes priority over the Bedtime sensor, which carries on turning on and off with no effect.

Coming home on the day the event is due to end finishes it there and then, so there's no need to match the calendar to the exact time you get back. Coming home on any earlier day leaves the alarm armed, as does anyone who is always shown as home, for example without location sharing switched on. This is the **Coming home ends Away and Vacation events on their last day** switch, in the **Advanced - Occupancy** section, which is on by default.

When the event ends during bedtime, the alarm goes to `armed_night`, or stays `armed_away` until someone is home. When it ends at any other time, the alarm is armed away if nobody is home, otherwise disarmed during the day, or `armed_home` after sunset.

Sunset still arms the alarm on a day with one of these calendar events, once the event has ended. The sunset [trigger](https://autoarm.rhizomatics.org.uk/automated_arming/#triggers) is only off by default on days with a `disarmed`, `armed_home` or `armed_night` calendar event.
