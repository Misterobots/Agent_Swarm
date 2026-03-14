from authentik.providers.oauth2.models import OAuth2Provider
# Update Redirect URI
p = OAuth2Provider.objects.get(name='Grafana')
p.redirect_uris = 'http://localhost/login/generic_oauth'
p.save()
print("REDIRECT_UPDATED")
