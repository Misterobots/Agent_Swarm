from authentik.providers.oauth2.models import OAuth2Provider
p = OAuth2Provider.objects.get(name='Grafana')
with open('/tmp/config_dump.txt', 'w') as f:
    f.write(f"ID={p.client_id}\n")
    f.write(f"SECRET={p.client_secret}\n")
    f.write(f"REDIRECTS={p.redirect_uris}\n")
