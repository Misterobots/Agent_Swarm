from authentik.flows.models import Flow
for f in Flow.objects.filter(slug__contains='provider'):
    print(f"{f.slug}::{f.pk}")
