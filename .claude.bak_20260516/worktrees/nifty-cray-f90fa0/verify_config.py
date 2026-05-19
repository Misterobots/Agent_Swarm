from authentik.providers.oauth2.models import OAuth2Provider
p = OAuth2Provider.objects.get(name='Grafana')
print(f"ID: {p.client_id}")
print(f"SECRET: {p.client_secret}")
print(f"REDIRECTS: {p.redirect_uris}")
