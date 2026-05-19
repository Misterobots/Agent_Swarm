import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.providers.proxy.models import ProxyProvider, ProxyMode
from authentik.core.models import Application
from authentik.flows.models import Flow

# Get default flows
auth_flow = Flow.objects.filter(slug__icontains='authorization').first()
print(f"Using auth flow: {auth_flow.name if auth_flow else 'None'}")

# Services to protect
services = [
    {"name": "Agent UI", "slug": "agent-ui", "external_host": "http://localhost:8501", "internal_host": "http://agent_ui:8501"},
    {"name": "ComfyUI", "slug": "comfyui", "external_host": "http://localhost:8188", "internal_host": "http://comfyui_gpu:8188"},
    {"name": "OpenHands", "slug": "openhands", "external_host": "http://localhost:3002", "internal_host": "http://openhands_sandbox:3000"},
]

for svc in services:
    print(f"Creating provider for {svc['name']}...")
    provider, created = ProxyProvider.objects.update_or_create(
        name=f"{svc['name']} Provider",
        defaults={
            "external_host": svc["external_host"],
            "internal_host": svc["internal_host"],
            "mode": ProxyMode.FORWARD_SINGLE,
            "authorization_flow": auth_flow,
        }
    )
    status = "created" if created else "updated"
    print(f"  Provider {status}: {provider.name}")
    app, created = Application.objects.update_or_create(
        slug=svc["slug"],
        defaults={
            "name": svc["name"],
            "provider": provider,
        }
    )
    status = "created" if created else "updated"
    print(f"  Application {status}: {app.name}")

print("Done!")
