from authentik.tenants.models import Tenant
t = Tenant.objects.first()
t.domain = "localhost"
t.default = True
t.save()
print(f"TENANT_CONFIG: Domain={t.domain}, Default={t.default}")
