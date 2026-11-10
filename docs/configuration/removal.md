# Removing Auto Arm

## Remove the Integration Entry

1. Go to **Settings** > **Devices & Services** and select **Auto Arm**
2. Click the three-dot menu and select **Delete**

This also removes the Auto Arm device and its entities.

## Uninstall from the Marketplace

Go to **Settings → Marketplace**, open **Auto Arm**, and choose **Uninstall** from the three dots menu. It can't be uninstalled while it's still set up, so either remove the integration entry first (above), or choose **Delete and uninstall**, which also deletes its device and entities.

Before Home Assistant 2026.11, open **HACS**, find **Auto Arm**, choose **Remove** from the three dots menu, then restart Home Assistant.

## Manual Removal

1. Delete the `custom_components/autoarm` directory
2. Remove the `autoarm:` section from your `configuration.yaml` if present
3. Restart Home Assistant

## Cleaning Up

After removal, you may also want to:

- Delete any Auto Arm-related automations or scripts you created
- Remove mobile notification actions configured for Auto Arm
- Remove any calendar entities that were created solely for Auto Arm scheduling
