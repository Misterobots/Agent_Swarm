"""Delete only the dedicated staging registration through Authentik's Django shell."""
from django.db import transaction
from authentik.core.models import Application

with transaction.atomic():
    app = Application.objects.get(slug="memex-qwen38-staging")
    provider = app.provider
    assert str(app.pk) == "76638bb1-581b-4476-8ac0-00a4e4da0a5e"
    assert provider.pk == 18 and provider.client_id == "memex-qwen38-staging"
    app.delete()
    provider.delete()
print("Removed only Memex Qwen38 staging application/provider18")
