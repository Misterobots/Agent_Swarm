from authentik.tenants.models import Tenant
t = Tenant.objects.first()
print(f"FIELDS: {[f.name for f in Tenant._meta.get_fields()]}")
