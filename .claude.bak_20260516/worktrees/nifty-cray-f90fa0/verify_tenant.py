from authentik.tenants.models import Tenant
t = Tenant.objects.first()
# Setting domain to specific value enforces check.
# Is there a way to disable? 
# Usually 'authentik_server' should work if Grafana calls 'http://authentik_server:9000'.
# BUT Grafana might be sending 'Host: authentik_server:9000'.
# Let's ensure 'authentik_server' is what we set.
t.domain = "authentik_server" 
t.save()
print(f"TENANT_DOMAIN: {t.domain}")

# Also check if there are other tenants?
print(f"COUNT: {Tenant.objects.count()}")
