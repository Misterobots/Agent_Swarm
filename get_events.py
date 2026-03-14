from authentik.events.models import Event
from django.forms.models import model_to_dict
import json

# Get last 5 events
events = Event.objects.all().order_by('-created')[:5]
for e in events:
    print(f"ACTION: {e.action} | USER: {e.user} | CONTEXT: {e.context}")
