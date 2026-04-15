---
title: "Tutorial: IoT Automation"
---

# Create IoT Automation

Control smart home devices through natural language chat commands.

## What You'll Learn

- How Agent Swarm connects to Home Assistant
- How to issue device commands via chat
- How to create automation routines

## Prerequisites

- Home Assistant running and accessible
- Devices configured in Home Assistant
- `HA_URL` and `HA_TOKEN` set in `network.env`

## Step 1: Verify Connection

```bash
curl -s -H "Authorization: Bearer $HA_TOKEN" \
    http://<ha-ip>:8123/api/states | python -m json.tool | head -20
```

You should see a list of entity states.

## Step 2: Simple Commands

In the Hive UI, try:

> Turn on the living room lights

The Router classifies this as `iot_control` and routes to the IoT Agent, which calls the Home Assistant API.

## Step 3: Query Device State

> What's the temperature in the bedroom?

The IoT Agent queries the relevant sensor entity and responds with the current value.

## Step 4: Complex Commands

> Set the living room lights to 50% brightness and warm white

The agent translates this into the appropriate Home Assistant service call with brightness and color temperature parameters.

## Step 5: Automations via Chat

> Every weekday at 7am, turn on the kitchen lights and set the thermostat to 72

This creates a Home Assistant automation through the API.

## Example Commands

| Command | What Happens |
|---------|-------------|
| "Turn off all lights" | Calls `light.turn_off` for all light entities |
| "Lock the front door" | Calls `lock.lock` for the door lock entity |
| "Is the garage door open?" | Queries the garage door cover entity state |
| "Set thermostat to 68" | Calls `climate.set_temperature` |

## Next Steps

- [User Guide: IoT Control](../user-guide/iot-control.md) — full IoT reference
- [Modules: Home Assistant Tool](../modules/tools/home-assistant.md) — technical details
