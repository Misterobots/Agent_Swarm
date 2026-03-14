from authentik.tenants.models import Tenant
try:
    existing = Tenant.objects.get(domain='authentik_server')
    print(f"TENANT_EXISTS: {existing}")
except Tenant.DoesNotExist:
    t = Tenant.objects.create(schema_name='public', domain='authentik_server', default=False)
    print(f"TENANT_CREATED: {t}")
except Exception as e:
    print(f"ERROR: {e}")
