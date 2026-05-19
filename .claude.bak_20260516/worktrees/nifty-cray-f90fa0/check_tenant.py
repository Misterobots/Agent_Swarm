from authentik.tenants.models import Tenant
t = Tenant.objects.first()
print(f"TENANT: Domain='{t.domain}', Default={t.default}")
# If default=True, it should work for any host.
# Let's try to add 'authentik_server' as a domain?
# Tenants can only have one domain?
# Actually, maybe we accept "authentik_server" by Clearing the domain?
