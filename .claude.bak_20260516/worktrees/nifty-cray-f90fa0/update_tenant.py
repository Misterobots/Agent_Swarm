from authentik.tenants.models import Tenant
t = Tenant.objects.first()
print(f"CURRENT_DOMAIN: {t.domain}")
# Update to allow everything or specific docker host
# Usually deleting the domain makes it default to everything? 
# Or enforcing a default. 
# Let's try setting it to 'authentik_server' or keeping localhost but ensuring it serves.
# Actually, the most robust way for internal docker comms is usually just ensuring the Tenant matches.
# Let's set it to valid docker hostname.
if 'authentik_server' not in t.domain:
    t.domain = "authentik_server"
    t.save()
    print("UPDATED_DOMAIN: authentik_server")
else:
    print("DOMAIN_OK")
