from authentik.tenants.models import Tenant
import sys

try:
    with open('/tmp/tenant_status.txt', 'w') as f:
        f.write("--- START ---\n")
        tenants = Tenant.objects.all()
        for t in tenants:
            f.write(f"ID={t.pk} DOMAIN={t.domain} DEFAULT={t.default}\n")
            if t.default:
                t.domain = 'authentik_server'
                t.save()
                f.write(f"UPDATED_DEFAULT_TO: {t.domain}\n")
        f.write("--- END ---\n")
except Exception as e:
    with open('/tmp/tenant_error.txt', 'w') as f:
        f.write(str(e))
