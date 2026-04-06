"""Create Grafana OAuth2 provider and application in Authentik.

Consolidates the former create_resources.py and create_resources_file.py scripts.

Usage:
  python create_resources.py                          # print to stdout
  python create_resources.py --output /tmp/grafana_creds.txt  # write to file
"""
import argparse

from authentik.providers.oauth2.models import OAuth2Provider, ClientTypes
from authentik.core.models import Application
from authentik.flows.models import Flow

def run(output_path=None):
    flow = Flow.objects.get(slug='default-provider-authorization-explicit-consent')

    provider, created = OAuth2Provider.objects.get_or_create(
        name='Grafana',
        defaults={
            'authorization_flow': flow,
            'client_type': ClientTypes.CONFIDENTIAL,
            'redirect_uris': 'http://localhost:3000/login/generic_oauth',
        }
    )

    app, app_created = Application.objects.get_or_create(
        name='Grafana',
        defaults={
            'slug': 'grafana',
            'provider': provider
        }
    )

    lines = [
        f"GRAFANA_CLIENT_ID={provider.client_id}",
        f"GRAFANA_CLIENT_SECRET={provider.client_secret}",
    ]
    if output_path:
        with open(output_path, 'w') as f:
            f.write("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Grafana OAuth2 resources")
    parser.add_argument("--output", default=None, help="Write credentials to file instead of stdout")
    args = parser.parse_args()
    run(output_path=args.output)
