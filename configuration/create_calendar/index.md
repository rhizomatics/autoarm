# Create a Calendar

Source: https://autoarm.rhizomatics.org.uk/configuration/create_calendar/

This *How To* will show you how to create a new calendar dedicated for controlling alarm control panel state. This is one way of using Auto Arm, you can choose to use [other types of calendars](https://www.home-assistant.io/integrations/?cat=calendar), reuse events from existing calendars, or mix-n-match.

## Add a Local Calendar

Use the button, or follow the manual steps:

1. From the *Settings* | *Integration* screen, choose **Add Integration**.
1. From this dialogue, choose **Local Calendar**
1. Configure the integration by choosing its name

## Configure Auto Arm

UI and YAML split

Calendar entities, and what happens when an event ends, are now configured via the Auto Arm **Options** UI. Per-calendar `state_patterns` and `poll_interval`, and the top-level `notify_grace_period`, remain in YAML.

Select the calendar entity in **Settings** > **Devices & Services** > **Auto Arm** > **Configure**.

Then add the per-calendar details in YAML, in this example `Alarm Control` is the name of the calendar:

```yaml
autoarm:
    calendar_control:
      calendars:
        - entity_id: calendar.alarm_control
          state_patterns:
              disarmed: Disarmed
```

This calendar is going to be used very simply to disarm the alarm during set periods, and let Auto Arm automatically handle the other times.

## Access the Calendar

If you don't have a **Calendar** option in the Home Assistant side-bar, then go to the personal settings ( bottom left corner, with your name against it) and change the visibility as:

## Setup a Disarm Schedule

Now that you have access to the calendar screen, add a recurring event for disarming.

## Changing your Mind

Once the event is created, double-click on a day to change it. You get the choice of changing just that day or all the recurring entries. Similarly you can delete one day from a recurring entry without affecting all the other ones. This makes it easy to do some one-off tuning for some days.

## Adding Vacations

You may have vacation events already on another calendar integration ( like Remote or Google Calendar ), or may want to add them to this one.

Here's how that might look:

```yaml
autoarm:
    calendar_control:
      - entity_id: calendar.alarm_control
        state_patterns:
            disarmed: Disarmed
      - entity_id: calendar.family_happenings
        state_patterns:
            armed_vacation:
              - Camping Trip.*
              - .*Holidays.*
            armed_away:
              - Work Trip.*
```

## What to do when no event

While a calendar could have events covering every minute of every day, its much less work to only define what is needed, such as what's the right time to arm at night, or when vacations start and end.

What happens when an event ends, and there's no other event live, is set in the **Advanced** section of the Auto Arm **Options**, separately for armed and disarmed events. See [When an Event Ends](https://autoarm.rhizomatics.org.uk/automated_arming/#when-an-event-ends) for the choices.
