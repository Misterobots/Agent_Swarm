from authentik.providers.oauth2.models import OAuth2Provider
p = OAuth2Provider.objects.get(name='Grafana')
p.client_secret = 'simple_secret_12345'
p.save()
print("SECRET_UPDATED")
