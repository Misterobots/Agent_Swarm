from authentik.core.models import Application
a = Application.objects.first()
slug = a.slug
with open('/tmp/slug.txt', 'w') as f:
    f.write(slug)
print(f"WROTE_SLUG: {slug}")
