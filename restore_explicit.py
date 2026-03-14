from authentik.providers.oauth2.models import OAuth2Provider
from authentik.flows.models import Flow

p = OAuth2Provider.objects.get(name='Grafana')
# Revert to standard flow
flow = Flow.objects.get(slug='default-provider-authorization-explicit-consent')
p.authorization_flow = flow
p.save()
print(f"PROVIDER_RESTORED: {p.name} -> {flow.slug}")
