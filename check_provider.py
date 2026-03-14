import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

p = OAuth2Provider.objects.get(name='Grafana')

# Write output to file
with open('/tmp/provider_info.txt', 'w') as f:
    f.write(f"include_claims_in_id_token: {p.include_claims_in_id_token}\n")
    f.write(f"client_type: {p.client_type}\n")
    f.write(f"sub_mode: {p.sub_mode}\n")
    f.write("Scope Mappings:\n")
    for s in p.property_mappings.all():
        f.write(f"  - {s.name}\n")
    f.write("Available Mappings:\n")
    for s in ScopeMapping.objects.all():
        f.write(f"  - {s.name} (scope: {s.scope_name})\n")

print("Done - check /tmp/provider_info.txt")
