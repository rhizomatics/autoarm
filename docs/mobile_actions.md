# Mobile Actions

AutoArm listens out for the result of [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/) with the following `action` values:

| Action Key         |
| ------------------ |
| ALARM_PANEL_DISARM |
| ALARM_PANEL_RESET  |
| ALARM_PANEL_AWAY   |

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

 If you want to send to e-mail and mobile then this will fail with a notify group because of
 the `actions` in the `data` field that aren't supported by other notification platforms. The
 best way to resolve that is with [Supernotify](https://supernotify.rhizomatics.org.uk) which will
 tune each message for the underlying transport ( mobile apps, and also e-mail, text, chime etc.)
 along with lots of other tuning options.
