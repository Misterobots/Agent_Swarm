import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import User

for user in User.objects.all():
    print(f"User: {user.username}, Email: '{user.email}', Name: {user.name}")
