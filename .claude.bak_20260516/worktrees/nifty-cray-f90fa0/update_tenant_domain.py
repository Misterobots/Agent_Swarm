from authentik.tenants.models import Tenant
t = Tenant.objects.first()
t.domain = "authentik_server"
t.save()
print(f"TENANT_UPDATED: Domain='{t.domain}', Default={t.default}")
