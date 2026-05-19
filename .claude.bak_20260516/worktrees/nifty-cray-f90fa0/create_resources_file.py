from authentik.providers.oauth2.models import OAuth2Provider, ClientTypes
from authentik.core.models import Application
from authentik.flows.models import Flow

flow = Flow.objects.get(slug='default-provider-authorization-explicit-consent')

provider, created = OAuth2Provider.objects.get_or_create(
    name='Grafana',
    defaults={
        'authorization_flow': flow,
        'client_type': ClientTypes.CONFIDENTIAL,
        'redirect_uris': 'http://localhost:3000/login/generic_oauth',
    }
)

app, app_created = Application.objects.get_or_create(
    name='Grafana',
    defaults={
        'slug': 'grafana',
        'provider': provider
    }
)

with open('/tmp/grafana_creds.txt', 'w') as f:
    f.write(f"CID={provider.client_id}\n")
    f.write(f"CSC={provider.client_secret}\n")
