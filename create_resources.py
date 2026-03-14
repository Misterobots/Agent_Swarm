from authentik.providers.oauth2.models import OAuth2Provider, ClientTypes
from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.core.models import PropertyMapping

flow = Flow.objects.get(slug='default-provider-authorization-explicit-consent')

# Create Grafana Provider
provider, created = OAuth2Provider.objects.get_or_create(
    name='Grafana',
    defaults={
        'authorization_flow': flow,
        'client_type': ClientTypes.CONFIDENTIAL,
        'redirect_uris': 'http://localhost:3000/login/generic_oauth',
    }
)
# Ensure default mappings are attached if created
if created:
    # Basic mappings (email, profile, openid)
    # Finding them by name is tricky as names vary. 
    # But usually creating a provider via UI attaches them.
    # Without them, user info might be empty.
    # We can try to find 'Authentik default OAuth Mapping: OpenID properties'
    pass

# Create Grafana App
app, app_created = Application.objects.get_or_create(
    name='Grafana',
    defaults={
        'slug': 'grafana',
        'provider': provider
    }
)

print(f"GRAFANA_CLIENT_ID={provider.client_id}")
print(f"GRAFANA_CLIENT_SECRET={provider.client_secret}")
