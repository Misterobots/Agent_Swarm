import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping

try:
    p = OAuth2Provider.objects.get(name='Grafana')
    print(f"Found provider: {p.name}")
    print(f"Current scope mappings count: {p.property_mappings.count()}")
    
    # Get all default scope mappings
    openid = ScopeMapping.objects.filter(name__icontains='openid').first()
    profile = ScopeMapping.objects.filter(name__icontains='profile').first()
    email = ScopeMapping.objects.filter(name__icontains='email').first()
    
    print(f"OpenID mapping: {openid}")
    print(f"Profile mapping: {profile}")
    print(f"Email mapping: {email}")
    
    # Add all scope mappings
    if openid:
        p.property_mappings.add(openid)
        print("Added openid")
    if profile:
        p.property_mappings.add(profile)
        print("Added profile")
    if email:
        p.property_mappings.add(email)
        print("Added email")
        
    p.save()
    print("Saved provider")
    print(f"New scope mappings count: {p.property_mappings.count()}")
except Exception as e:
    print(f"Error: {e}")
