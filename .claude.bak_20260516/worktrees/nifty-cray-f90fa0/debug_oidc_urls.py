from django.urls import reverse
from authentik.providers.oauth2.models import OAuth2Provider

# Get slug
try:
    p = OAuth2Provider.objects.get(name='Grafana')
    # Assuming one application
    app = p.application_set.first()
    slug = app.slug if app else 'grafana'
    
    print(f"SLUG: {slug}")
    
    # Generic URLs (if implicit)
    print(f"AUTH_URL_GENERIC: {reverse('authentik_providers_oauth2:authorize')}")
    print(f"TOKEN_URL_GENERIC: {reverse('authentik_providers_oauth2:token')}")
    
    # Specific URLs?
    # Usually they take parameters?
    # Let's check discovery
    print(f"DISCOVERY_URL: {reverse('authentik_providers_oauth2:provider-discovery', kwargs={'slug': slug})}")

except Exception as e:
    print(f"Error: {e}")
