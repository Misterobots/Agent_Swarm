import os
import requests
import json
import logging

logger = logging.getLogger("IoT_Ops")

# Configuration
HASS_HOST = os.getenv("HASS_HOST", "http://homeassistant.local:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "dummy_token")
MOCK_MODE = os.getenv("IOT_MOCK_MODE", "True").lower() == "true"

# Mock Database
MOCK_DB = {
    "light.studio_main": {"state": "on", "attributes": {"brightness": 255, "friendly_name": "Studio Main Lights"}},
    "light.kitchen_strip": {"state": "off", "attributes": {"friendly_name": "Kitchen Under Cabinet"}},
    "sensor.living_room_temp": {"state": "72.5", "attributes": {"unit_of_measurement": "°F", "friendly_name": "Living Room Temp"}},
    "switch.3d_printer": {"state": "off", "attributes": {"friendly_name": "Bambu Lab X1C Power"}},
    "lock.front_door": {"state": "locked", "attributes": {"friendly_name": "Front Door Lock"}} # Sensitive
}

def get_states(domain=None):
    """
    Fetches states of all entities or filters by domain.
    """
    if MOCK_MODE:
        logger.info("[IoT] Using Mock Data for get_states")
        results = []
        for entity_id, data in MOCK_DB.items():
            if domain and not entity_id.startswith(domain):
                continue
            results.append({
                "entity_id": entity_id,
                "state": data["state"],
                "attributes": data["attributes"]
            })
        return json.dumps(results, indent=2)

    try:
        headers = {"Authorization": f"Bearer {HASS_TOKEN}", "content-type": "application/json"}
        response = requests.get(f"{HASS_HOST}/api/states", headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        if domain:
            data = [d for d in data if d["entity_id"].startswith(domain)]
            
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error fetching states: {e}"

def call_service(domain, service, entity_id, **kwargs):
    """
    Calls a service (e.g., light.turn_on) on an entity.
    """
    if MOCK_MODE:
        logger.info(f"[IoT] MOCK ACTION: {domain}.{service} on {entity_id} with {kwargs}")
        
        # Update Mock DB logic
        if entity_id in MOCK_DB:
            if service == "turn_on":
                MOCK_DB[entity_id]["state"] = "on"
                if "brightness" in kwargs:
                     MOCK_DB[entity_id]["attributes"]["brightness"] = kwargs["brightness"]
            elif service == "turn_off":
                MOCK_DB[entity_id]["state"] = "off"
                
        return f"SUCCESS: Called {domain}.{service} on {entity_id}. (Simulated)"

    try:
        headers = {"Authorization": f"Bearer {HASS_TOKEN}", "content-type": "application/json"}
        payload = {"entity_id": entity_id}
        payload.update(kwargs)
        
        url = f"{HASS_HOST}/api/services/{domain}/{service}"
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        
        return f"SUCCESS: Executed {domain}.{service}"
    except Exception as e:
        return f"Error calling service: {e}"
