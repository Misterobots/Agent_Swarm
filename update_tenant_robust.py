from authentik.tenants.models import Tenant
try:
    print("--- LIST TENANTS ---")
    for t in Tenant.objects.all():
        print(f"ID={t.pk} SCHEMA={t.schema_name} DOMAIN={t.domain} DEFAULT={t.default}")

    print("--- UPDATE DEFAULT ---")
    t = Tenant.objects.get(default=True)
    print(f"FOUND: {t.domain}")
    t.domain = 'authentik_server'
    t.save()
    print(f"UPDATED: {t.domain}")

except Exception as e:
    import traceback
    traceback.print_exc()
