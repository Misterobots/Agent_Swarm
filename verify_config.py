"""Verify Grafana OAuth2 provider configuration in Authentik.

Consolidates the former verify_config.py and verify_config_file.py scripts.

Usage:
  python verify_config.py                       # print to stdout
  python verify_config.py --output /tmp/config_dump.txt  # write to file
"""
import argparse

from authentik.providers.oauth2.models import OAuth2Provider

def run(output_path=None):
    p = OAuth2Provider.objects.get(name='Grafana')
    lines = [
        f"ID={p.client_id}",
        f"SECRET={p.client_secret}",
        f"REDIRECTS={p.redirect_uris}",
    ]
    if output_path:
        with open(output_path, 'w') as f:
            f.write("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Grafana OAuth2 config")
    parser.add_argument("--output", default=None, help="Write to file instead of stdout")
    args = parser.parse_args()
    run(output_path=args.output)
