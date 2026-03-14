from authentik.providers.oauth2.models import OAuth2Provider
p = OAuth2Provider.objects.get(name='Grafana')
with open('/tmp/s.txt', 'w') as f:
    f.write(p.client_secret)
