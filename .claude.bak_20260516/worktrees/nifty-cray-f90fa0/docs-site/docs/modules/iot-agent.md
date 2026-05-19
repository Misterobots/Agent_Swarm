---
title: "Module: IoT Agent"
---

# IoT Agent

Home Assistant integration for smart device control.

## Files

| File | Purpose |
|------|---------|
| `agents/specialized/iot_agent.py` | IoT control agent |
| `agents/tools/ha_tools.py` | Home Assistant tool functions |

## Capabilities

| Tool | Description |
|------|-------------|
| `ha_call_service` | Call any HA service |
| `ha_turn_on` | Turn on a device |
| `ha_turn_off` | Turn off a device |
| `ha_get_state` | Query device state |
| `ha_set_temperature` | Set thermostat |
| `ha_set_brightness` | Adjust light brightness |

## Natural Language Processing

The IoT Agent translates natural language to HA API calls:

| User Says | API Call |
|-----------|----------|
| "Turn on the living room lights" | `ha_turn_on("light.living_room")` |
| "Set bedroom to 72°F" | `ha_set_temperature("climate.bedroom", 72)` |
| "Is the garage door open?" | `ha_get_state("cover.garage_door")` |

## Home Assistant Configuration

| Property | Value |
|----------|-------|
| URL | `http://192.168.2.100:8123` |
| Auth | Long-lived access token |
| API | REST API v2 |

## IoT Dev Mode

The `IOT_DEV` intent handles firmware and hardware development:

- ESPHome configuration generation
- Wokwi simulation setup
- MQTT topic management
- Circuit design assistance

## Security

IoT commands are gated by JWT-ACE tokens with `level: L5`. Only requests classified as `IOT_CONTROL` receive HA tool access.

## Related

- [User Guide: IoT Control](../user-guide/iot-control.md) — user-facing guide
- [Module: Tools: Home Assistant](tools/home-assistant.md) — tool details


