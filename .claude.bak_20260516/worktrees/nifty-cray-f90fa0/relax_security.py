from authentik.tenants.models import Tenant
from authentik.providers.oauth2.models import OAuth2Provider

# 1. Fix Tenant (Enable Default to handle all hosts)
t = Tenant.objects.first()
t.domain = "localhost" # Primary for Admin
t.default = True # Handle authentik_server too
t.save()
print("TENANT_UPDATED_DEFAULT")

# 2. Fix Provider (Wildcard Redirect)
p = OAuth2Provider.objects.get(name='Grafana')
p.redirect_uris = ".*" # Regex match all
p.save()
print("PROVIDER_REDIRECT_WILDCARD")
