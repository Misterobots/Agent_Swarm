---
title: IoT Control
---

# IoT Control

Control Home Assistant devices, prototype ESP32/Arduino firmware, and simulate circuits with Wokwi.

## How to Access

- **Chat**: Describe what you want — the router detects `IOT_CONTROL` or `IOT_DEV` intent
- **Home Assistant**: Direct at `http://{{ home_assistant_ip }}:8123`

## Quick Example

> *"Turn on the living room lights"*

The router classifies this as `IOT_CONTROL` and dispatches to the Home Assistant tool, which calls `call_service("light.turn_on", "light.living_room")`.

## Detailed Usage

### Device Control

The system integrates with Home Assistant via its REST API. Available operations:

| Tool Function | Description |
|---------------|-------------|
| `get_state(entity_id)` | Read current state of a device |
| `call_service(domain, service, entity_id)` | Execute a Home Assistant service |
| `turn_on(entity_id)` | Shortcut for turning on devices |
| `turn_off(entity_id)` | Shortcut for turning off devices |

### Natural Language Examples

| Command | Action |
|---------|--------|
| "Turn on the kitchen light" | `light.turn_on` → `light.kitchen` |
| "What's the temperature in the bedroom?" | `get_state` → `sensor.bedroom_temperature` |
| "Lock the front door" | `lock.lock` → `lock.front_door` |
| "Set the thermostat to 72" | `climate.set_temperature` → 72°F |

### Hardware Prototyping (IOT_DEV)

The `IOT_DEV` intent handles firmware development:

- **ESPHome**: Compile and upload firmware to ESP32/ESP8266 devices
- **Wokwi**: Simulate Arduino/ESP32 circuits in-browser
- **MQTT**: Publish and subscribe to MQTT topics

### Wokwi Simulation

Create and simulate circuits without physical hardware:

```
"Create an ESP32 circuit with a temperature sensor and LED indicator"
```

The system generates a Wokwi simulation configuration with parts, wiring, and firmware code.

## Tips & Common Patterns

!!! tip "Entity Names"
    Use natural names — the system maps them to Home Assistant entity IDs. If ambiguous, it will ask for clarification.

!!! tip "Automation Scripts"
    Ask the system to write Home Assistant automation YAML, then apply it through the API.

## Related

- [Module: Home Assistant Tool](../modules/tools/home-assistant.md)
- [Module: Wokwi Tool](../modules/tools/mqtt.md)
- [Module: ESPHome Tool](../modules/tools/mqtt.md)
- [Tutorial: Control Home Devices](../tutorials/iot-automation.md)
- [Tutorial: Simulate IoT](../tutorials/iot-automation.md)


