# Bedtime Recipe

A simple setup for a home that's lived in most days, with no YAML:

- **Armed night** for a fixed bedtime every day, from a [Time of Day](https://www.home-assistant.io/integrations/tod/) sensor
- **Armed home** from sunset until bedtime, when sunset comes first
- **Disarmed** when bedtime ends, whether or not the sun is up yet
- **Armed away** whenever everyone is out
- A calendar for vacations and other planned time away, with no need to switch the bedtime sensor off for them

## Set Up

1. Create a **Bedtime** sensor in **Settings** > **Devices & Services** > **Helpers** > **Create Helper** > **Times of the Day**, on at 23:00 and off at 07:00, or whatever suits.
2. Have a calendar for vacations and time away. If you don't have one, see [Create a Calendar](../create_calendar.md).
3. In **Settings** > **Devices & Services** > **Auto Arm** > **Configure**:

| Section         | Setting                                         | Value                 |
|-----------------|-------------------------------------------------|-----------------------|
|                 | **Calendars to use for arming schedules**       | The calendar          |
|                 | **People for occupancy based arming**           | Everyone who lives in |
| **Time of Day** | **Armed night**                                 | The Bedtime sensor    |
| **Advanced**    | **Default arming state when occupied during day** | Disarmed            |
| **Advanced**    | **Default arming state when occupied at night** | Armed home            |

Everything else is left at its default.

## An Ordinary Day

With someone home, and sunset at 18:00:

| Time  | What happens       | Alarm state   |
|-------|--------------------|---------------|
| 07:00 | Bedtime sensor off | `disarmed`    |
| 18:00 | Sunset             | `armed_home`  |
| 23:00 | Bedtime sensor on  | `armed_night` |

Sunrise makes no difference. In summer it comes during bedtime, and is ignored. In winter it comes after bedtime has ended and the alarm is already disarmed. If sunset comes after bedtime has started, it's ignored too.

If everyone is out, the alarm is `armed_away` at any time of day. Coming home during bedtime sets it to `armed_night`.

## Vacations and Time Away

Add a calendar event with **Vacation** or **Away** in its title. While the event is live it takes priority over the Bedtime sensor, which carries on turning on and off with no effect.

When the event ends during bedtime, the alarm goes to `armed_night`, or stays `armed_away` until someone is home. When it ends at any other time, the alarm is disarmed if someone is home, or armed away if not.

On a day with one of these calendar events, sunset doesn't arm the alarm, since the sunrise and sunset [triggers](../../automated_arming.md#triggers) are off by default on calendar days. Bedtime still does.
