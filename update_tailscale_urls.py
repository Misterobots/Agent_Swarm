import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.providers.proxy.models import ProxyProvider

# Update all proxy providers to use the Tailscale hostname
tailscale_host = "http://justin-pc"

for provider in ProxyProvider.objects.all():
    # Update external host to use Tailscale
    old_host = provider.external_host
    if "localhost" in old_host:
        # Keep the port and path, just change the host
        provider.external_host = old_host.replace("localhost", "justin-pc")
        provider.save()
        print(f"Updated {provider.name}: {old_host} -> {provider.external_host}")
    else:
        print(f"Skipped {provider.name}: {old_host}")

print("\nDone!")
