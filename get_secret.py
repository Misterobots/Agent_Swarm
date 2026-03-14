import sys
from authentik.providers.oauth2.models import OAuth2Provider
p = OAuth2Provider.objects.get(name='Grafana')
print(f"SECRET_BEGIN:{p.client_secret}:SECRET_END")
sys.exit(0)
