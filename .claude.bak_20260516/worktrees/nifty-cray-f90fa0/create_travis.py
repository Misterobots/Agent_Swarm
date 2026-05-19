import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import User, Group

# Create Travis's account
travis, created = User.objects.update_or_create(
    username="travis",
    defaults={
        "name": "Travis",
        "email": "tdub84@example.com",  # Update with actual email
        "is_active": True,
    }
)

if created:
    # Set a temporary password
    travis.set_password("Welcome123!")
    travis.save()
    print(f"Created user: {travis.username}")
    print(f"Temporary password: Welcome123!")
    print("(User should change password on first login)")
else:
    print(f"User already exists: {travis.username}")

# Add to a collaborators group if it exists
collab_group, _ = Group.objects.get_or_create(name="Collaborators")
travis.ak_groups.add(collab_group)
print(f"Added {travis.username} to group: {collab_group.name}")

print("\nDone!")
