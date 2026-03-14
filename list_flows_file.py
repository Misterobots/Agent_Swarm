from authentik.flows.models import Flow
with open('/tmp/flows.txt', 'w') as f:
    for flow in Flow.objects.filter(slug__contains='provider'):
        f.write(f"{flow.slug}::{flow.pk}\n")
