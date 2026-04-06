"""List Authentik provider flows.

Consolidates the former list_flows.py and list_flows_file.py scripts.

Usage:
  python list_flows.py                          # print to stdout
  python list_flows.py --output /tmp/flows.txt  # write to file
"""
import argparse

from authentik.flows.models import Flow

def run(output_path=None):
    lines = []
    for flow in Flow.objects.filter(slug__contains='provider'):
        lines.append(f"{flow.slug}::{flow.pk}")

    if output_path:
        with open(output_path, 'w') as f:
            f.write("\n".join(lines) + "\n")
    else:
        for line in lines:
            print(line)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List Authentik provider flows")
    parser.add_argument("--output", default=None, help="Write to file instead of stdout")
    args = parser.parse_args()
    run(output_path=args.output)
