# Changelog

## 0.6.0
### Features
- Internal logic for automatic state calc replaced by regular Home Assistant conditions
- Configuration cleaned up into logical, extensible sections
### Internal
- All manual actions now recorded as interventions
- Regular housekeeping for interventions and calendar tracking
- Further typing with ChangeSource and AlarmControlPanelState
- Primary class documentation page
## 0.5.2
- Clean up dead code for mobile actions

## 0.5.1
- Clean up the pre-calendar bedtime config and mechanism
- Add new `occupied_daytime_state` config to allow choice, e.g. between `armed_home` and `disarmed`

## 0.5.0
- Productionizing of private code
- Component now reloadable
- Multiple calendar integration
