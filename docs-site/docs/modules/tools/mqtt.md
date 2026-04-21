---
title: "Tool: MQTT"
---

# MQTT Tool

Publish and subscribe to MQTT topics for IoT communication.

## Functions

| Function | Description |
|----------|-------------|
| `mqtt_publish(topic, payload)` | Publish a message to a topic |
| `mqtt_subscribe(topic)` | Subscribe and receive messages |

## Use Cases

- ESPHome device communication
- Custom IoT sensor data
- BMO satellite device commands

## Security

- Only accessible with `mqtt_publish` in JWT-ACE token
- Security level: L5

## Allowed Intents

`IOT_DEV`


