---
title: "Tool: Home Assistant"
---

# Home Assistant Tools

Functions for controlling smart home devices via Home Assistant.

## Functions

| Function | Parameters | Description |
|----------|------------|-------------|
| `ha_call_service` | `domain`, `service`, `entity_id`, `data` | Call any HA service |
| `ha_turn_on` | `entity_id` | Turn on a device |
| `ha_turn_off` | `entity_id` | Turn off a device |
| `ha_get_state` | `entity_id` | Query device state |
| `ha_set_temperature` | `entity_id`, `temperature` | Set thermostat |
| `ha_set_brightness` | `entity_id`, `brightness` | Adjust light (0–255) |

## Configuration

| Setting | Value |
|---------|-------|
| HA URL | `http://192.168.2.100:8123` |
| Auth | Long-lived access token (in `network.env`) |

## Security

- Only accessible with HA tools in JWT-ACE token
- Requires `IOT_CONTROL` intent classification
- Security level: L5
- All calls logged for audit

## Allowed Intents

`IOT_CONTROL`
