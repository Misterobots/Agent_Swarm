from authentik.tenants.models import Tenant
t = Tenant.objects.first()
print(f"CURRENT_DOMAIN: {t.domain}")
t.domain = "authentik_server"
t.save()
print(f"NEW_DOMAIN: {t.domain}")
