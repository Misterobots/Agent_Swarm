import os
import django
from django.conf import settings

# Setup Django Environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import User, Token, TokenIntents
from django.utils.timezone import now
from datetime import timedelta

def create_agent_token():
    try:
        # Get Admin User (default is usually 'akadmin')
        user = User.objects.filter(username='akadmin').first()
        if not user:
            print("ERROR: User 'akadmin' not found.")
            return

        # Check if token exists
        token_key = "agent-config-token-123" # Fixed key for easy retrieval/idempotency
        existing_token = Token.objects.filter(identifier='agent-config-token').first()
        
        if existing_token:
            print(f"TOKEN:{existing_token.key}")
            return

        # Create Token
        token = Token.objects.create(
            identifier='agent-config-token',
            user=user,
            intent=TokenIntents.INTENT_API,
            description='Agent Configuration Token (Automated)',
            expiring=False,
            key=token_key
        )
        print(f"TOKEN:{token.key}")

    except Exception as e:
        print(f"ERROR:{str(e)}")

if __name__ == "__main__":
    create_agent_token()
