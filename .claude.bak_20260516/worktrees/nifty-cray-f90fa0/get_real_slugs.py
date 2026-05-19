import os
import django
import sys

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.providers.oauth2.models import OAuth2Provider
from authentik.core.models import Application

print("--- DIAGNOSTIC START ---")
users = Application.objects.all()
for app in users:
    print(f"APP: Name='{app.name}', Slug='{app.slug}'")
    if app.provider:
        print(f"  PROVIDER: Name='{app.provider.name}', Type='{type(app.provider).__name__}', PK={app.provider.pk}")
        if isinstance(app.provider, OAuth2Provider):
            print(f"  CLIENT_ID: {app.provider.client_id}")

print("--- DIAGNOSTIC END ---")
