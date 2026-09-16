"""Run only in existing Authentik Django shell. Credential output is captured, never logged."""
import json
import secrets
from django.db import transaction
from authentik.core.models import Application, User
from authentik.providers.oauth2.models import OAuth2Provider, ScopeMapping
from authentik.policies.models import PolicyBinding
from authentik.crypto.models import CertificateKeyPair

slug = "memex-qwen38-staging"
with transaction.atomic():
    if Application.objects.filter(slug=slug).exists() or OAuth2Provider.objects.filter(client_id=slug).exists():
        raise RuntimeError("Staging registration already exists; inspect it before changing credentials")
    source = Application.objects.get(slug="memex")
    owner = User.objects.get(username="misterobots", is_active=True)
    provider = OAuth2Provider.objects.create(
        name="Memex Qwen38 isolated staging", client_id=slug,
        client_secret=secrets.token_urlsafe(48), client_type="confidential",
        authentication_flow=source.provider.authentication_flow,
        authorization_flow=source.provider.authorization_flow,
        invalidation_flow=source.provider.invalidation_flow,
        signing_key=CertificateKeyPair.objects.get(name="authentik Internal JWT Certificate"),
        _redirect_uris=[{"matching_mode": "strict", "url": "http://127.0.0.1:3319/oauth2/callback"}],
        include_claims_in_id_token=True, sub_mode="hashed_user_id",
    )
    provider.property_mappings.set(ScopeMapping.objects.filter(scope_name__in=["openid", "email", "profile"]))
    application = Application.objects.create(name="Memex Qwen38 isolated staging", slug=slug, provider=provider, policy_engine_mode="all", meta_launch_url="http://127.0.0.1:3319/api/auth/login")
    # Same inherited auth flows and source policy bindings, plus a staging owner restriction.
    for binding in PolicyBinding.objects.filter(target=source):
        PolicyBinding.objects.create(target=application, policy=binding.policy, group=binding.group, user=binding.user, order=binding.order, negate=binding.negate, enabled=binding.enabled, timeout=binding.timeout, failure_result=binding.failure_result)
    PolicyBinding.objects.create(target=application, user=owner, order=1000, enabled=True)
    print("STAGING_CREDENTIAL=" + json.dumps({"client_secret": provider.client_secret, "provider_id": provider.pk, "application_id": str(application.pk)}))
