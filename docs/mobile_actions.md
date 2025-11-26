# Mobile Actions

AutoArm listens out for the result of [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/) with the following `action` values:

## Supported Actions

| Action Key         |
| ------------------ |
| ALARM_PANEL_DISARM |
| ALARM_PANEL_RESET  |
| ALARM_PANEL_AWAY   |

## Add Action to a Mobile Push Notification

Here's how to send a notification to a mobile app, with a Disarm action:

```yaml
action: notify.mobile_app_<your_device_id_here>
data:
  message: "The noisy PIR has detected the kids again"
  data:
    actions:
      - action: "ALARM_PANEL_DISARM" # The key you are sending for the event
        title: "Disarm Alarm" # The button title
        icon: sfsymbols:bell.slash
```
