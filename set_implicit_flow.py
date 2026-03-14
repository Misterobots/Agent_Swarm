from authentik.providers.oauth2.models import OAuth2Provider
from authentik.flows.models import Flow

# Get Provider
p = OAuth2Provider.objects.get(name='Grafana')

# Get Implicit Flow
flow = Flow.objects.get(slug='default-provider-authorization-implicit-consent')

# Update Provider
p.authorization_flow = flow
p.save()

print(f"PROVIDER_UPDATED: {p.name} -> {flow.slug}")
