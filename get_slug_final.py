from authentik.core.models import Application
a = Application.objects.first()
print(f"SLUG_IS_{a.slug}_END")
