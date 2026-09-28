import os
import requests
import json
from typing import Optional, Dict, Any
from config import HOME_ASSISTANT_URL

class HomeAssistantTool:
    def __init__(self):
        self.base_url = HOME_ASSISTANT_URL
        self.token = os.getenv("HOME_ASSISTANT_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _call_api(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Helper to call HA API.
        """
        url = f"{self.base_url}/api/{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=5)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=5)
            else:
                return {"error": f"Unsupported method: {method}"}

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API Error {response.status_code}: {response.text}"}
        except Exception as e:
            return {"error": f"Connection Error: {e}"}

    def get_state(self, entity_id: str) -> Dict[str, Any]:
        """
        Get the state of a specific entity.
        """
        return self._call_api(f"states/{entity_id}")

    def call_service(self, domain: str, service: str, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a service (e.g., light.turn_on).
        """
        return self._call_api(f"services/{domain}/{service}", method="POST", data=service_data)

    def turn_on(self, entity_id: str, **kwargs) -> Dict[str, Any]:
        """
        Turn on an entity (light, switch, etc.).
        """
        domain = entity_id.split(".")[0]
        data = {"entity_id": entity_id}
        data.update(kwargs) # Merge brightness, color, etc.
        return self.call_service(domain, "turn_on", data)

    def turn_off(self, entity_id: str) -> Dict[str, Any]:
        """
        Turn off an entity.
        """
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_off", {"entity_id": entity_id})
