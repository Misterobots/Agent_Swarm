"""Run through the existing Authentik Django shell; prints no credentials."""
import json
from authentik.core.models import Application
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping
from authentik.policies.models import PolicyBinding
from authentik.crypto.models import CertificateKeyPair

app = Application.objects.get(slug="memex")
p = app.provider
print("STAGING_INSPECT=" + json.dumps({
    "application": {"pk": str(app.pk), "slug": app.slug, "policy_engine_mode": app.policy_engine_mode},
    "provider": {"pk": p.pk, "authentication_flow": str(p.authentication_flow_id), "authorization_flow": str(p.authorization_flow_id), "invalidation_flow": str(p.invalidation_flow_id)},
    "bindings": list(PolicyBinding.objects.filter(target=app).values("order", "policy_id", "group_id", "user_id", "negate", "enabled", "timeout", "failure_result")),
    "scopes": list(ScopeMapping.objects.filter(scope_name__in=["openid", "email", "profile"]).values("pk", "name", "scope_name")),
    "keys": list(CertificateKeyPair.objects.values("pk", "name")),
    "oauth_fields": [f.name for f in OAuth2Provider._meta.fields],
}, default=str))
stage = Application.objects.filter(slug="memex-qwen38-staging").first()
if stage:
    provider = OAuth2Provider.objects.get(pk=stage.provider_id)
    print("STAGING_AUDIT=" + json.dumps({
        "application_id": str(stage.pk), "provider_id": provider.pk,
        "policy_engine_mode": stage.policy_engine_mode,
        "redirect_allowlist": provider._redirect_uris,
        "flows_match_memex": all(getattr(provider, key) == getattr(p, key) for key in ["authentication_flow_id", "authorization_flow_id", "invalidation_flow_id"]),
        "app_only_bindings": list(PolicyBinding.objects.filter(target=stage).values("user__username", "policy_id", "group_id", "enabled", "negate", "order")),
    }, default=str))
