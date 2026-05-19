import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.outposts.models import Outpost, OutpostType, DockerServiceConnection
from authentik.providers.proxy.models import ProxyProvider
from authentik.core.models import Application

# Get or create the Docker connection for embedded outpost
docker_conn, created = DockerServiceConnection.objects.get_or_create(
    name="Local Docker Connection",
    defaults={
        "local": True,
    }
)
print(f"Docker connection: {docker_conn.name} ({'created' if created else 'existing'})")

# Get all proxy provider applications
proxy_apps = Application.objects.filter(
    provider__in=ProxyProvider.objects.all()
)
print(f"Found {proxy_apps.count()} proxy applications")

# Create or update the Outpost
outpost, created = Outpost.objects.update_or_create(
    name="Traefik Forward Auth Outpost",
    defaults={
        "type": OutpostType.PROXY,
        "service_connection": docker_conn,
    }
)
print(f"Outpost: {outpost.name} ({'created' if created else 'updated'})")

# Add all proxy applications to the outpost
for app in proxy_apps:
    outpost.providers.add(app.provider)
    print(f"  Added provider: {app.provider.name}")

outpost.save()
print("\nOutpost configured successfully!")
print(f"Outpost should be accessible at: /outpost.goauthentik.io/auth/traefik")
