"""Unauthenticated, no-inference checks of the live staging trust boundary."""
import json
import subprocess
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

paths = ["/dev", "/api/auth/me", "/api/backend/api/v1/identity", "/api/backend/v1/models"]
variants = {
    "anonymous": {},
    "forged_authentik": {"X-authentik-username": "misterobots", "X-authentik-uid": "4", "X-authentik-groups": "admin"},
    "forged_forwarded": {"X-Forwarded-User": "misterobots", "X-Auth-Request-User": "misterobots", "X-Auth-Request-Groups": "admin"},
    "forged_bearer": {"Authorization": "Bearer deliberately-invalid"},
    "forged_cookie": {"Cookie": "memex_qwen38_staging=deliberately-invalid"},
}
results = []
for path in paths:
    for label, headers in variants.items():
        try:
            with urlopen(Request("http://127.0.0.1:3319" + path, headers=headers), timeout=5) as response:
                status = response.status
        except HTTPError as exc:
            status = exc.code
        assert status == 401, (path, label, status)
        results.append({"path": path, "case": label, "status": status})

names = ["memex_qwen38_dev_20260915", "memex_qwen38_ui_20260915", "memex_qwen38_oauth", "memex_qwen38_proxy"]
# Inspect in memory; do not print environment secrets returned by Docker.
containers = json.loads(subprocess.check_output(["docker", "inspect", *names]))
for container in containers:
    assert set(container["NetworkSettings"]["Networks"]) == {"memex_qwen38_private"}
    bindings = container["HostConfig"]["PortBindings"] or {}
    if container["Name"] == "/memex_qwen38_proxy":
        assert bindings == {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "3319"}]}
    else:
        assert not bindings, container["Name"]
print(json.dumps({"checks": results, "private_container_boundary": "passed"}, indent=2))


class NoRedirectHandler(HTTPRedirectHandler):
    """Capture redirect responses instead of following them."""

    def http_error_302(self, req, fp, code, msg, headers):
        return fp

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


redirects = build_opener(NoRedirectHandler())
with redirects.open("http://127.0.0.1:3319/api/auth/login", timeout=5) as response:
    assert response.status == 302
    assert response.headers["Location"] == "http://127.0.0.1:3319/oauth2/start?rd=/dev"
with redirects.open("http://127.0.0.1:3319/oauth2/start?rd=/dev", timeout=5) as response:
    assert response.status == 302
    target = urlparse(response.headers["Location"])
    query = parse_qs(target.query)
    assert (target.scheme, target.netloc, target.path) == (
        "https", "auth.shivelymedia.com", "/application/o/authorize/"
    )
    assert query["client_id"] == ["memex-qwen38-staging"]
    assert query["redirect_uri"] == ["http://127.0.0.1:3319/oauth2/callback"]
    state_target = query["state"][0].split(":", 1)[1]
    assert state_target == "/dev"
with redirects.open(
    "http://127.0.0.1:3319/oauth2/start?rd=https://example.invalid/escape", timeout=5
) as response:
    target = urlparse(response.headers["Location"])
    query = parse_qs(target.query)
    assert query["redirect_uri"] == ["http://127.0.0.1:3319/oauth2/callback"]
    assert query["state"][0].split(":", 1)[1] == "/dev"
print(json.dumps({"redirect_contract": "passed", "external_origin": "http://127.0.0.1:3319"}))
