"""Protocol-level coverage for the in-memory pairing relay.

The deployed Authentik-protected host/guest flow still needs two authenticated
sessions; these tests isolate the relay contract so that gap is not confused
with untested application behavior.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pairing import routes


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(routes.router)
    return app


def test_pairing_relay_is_bidirectional_and_announces_peer():
    with TestClient(_app()) as client:
        created = client.post(
            "/api/v1/pairing/create",
            json={"display_name": "Host", "memex_url": "http://host"},
        )
        assert created.status_code == 200
        host_token = created.json()["token"]
        code = created.json()["code"]

        joined = client.post(
            f"/api/v1/pairing/join/{code}",
            json={"display_name": "Guest"},
        )
        assert joined.status_code == 200
        guest_token = joined.json()["token"]
        assert joined.json()["host_info"]["display_name"] == "Host"

        try:
            with client.websocket_connect(f"/api/v1/pairing/ws/{host_token}") as host:
                with client.websocket_connect(f"/api/v1/pairing/ws/{guest_token}") as guest:
                    assert host.receive_json() == {"type": "peer_joined", "role": "guest"}

                    guest.send_json({"type": "guest_message", "value": 1})
                    assert host.receive_json() == {
                        "type": "guest_message", "value": 1, "_from": "guest"
                    }

                    host.send_json({"type": "host_message", "value": 2})
                    assert guest.receive_json() == {
                        "type": "host_message", "value": 2, "_from": "host"
                    }
        finally:
            routes._rooms_by_code.clear()
            routes._rooms_by_token.clear()
