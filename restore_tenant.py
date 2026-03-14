from authentik.tenants.models import Tenant
t = Tenant.objects.first()
t.domain = "localhost"
t.save()
print("TENANT_RESTORED: localhost")
