from authentik.providers.oauth2.models import OAuth2Provider
from django.urls import reverse

p = OAuth2Provider.objects.get(name='Grafana')
# URLs are usually defined in API or by slug
# Let's try to construct it or find the slug
# Application slug?
apps = p.application_set.all()
for a in apps:
    print(f"APP_SLUG: {a.slug}")

print(f"PROVIDER_NAME: {p.name}")
# Try to simulate the URL construction
# usually /application/o/<app_slug>/... if implicit?
# Or /application/o/authorize/ ? 
# Let's check the property if it exists
try:
    print(f"URL: {p.url_token}")
except:
    pass
