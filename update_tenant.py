"""Unified tenant domain updater for Authentik.

Consolidates the former update_tenant.py, update_tenant_domain.py,
update_tenant_robust.py, and update_tenant_silent.py scripts.

Modes:
  conditional  - Only update if domain doesn't already match (default)
  force        - Unconditionally set the domain
  robust       - List all tenants, then update the default tenant
  silent       - Write output to /tmp/tenant_status.txt instead of stdout

Usage:
  python update_tenant.py                          # conditional (default)
  python update_tenant.py --mode force
  python update_tenant.py --mode robust
  python update_tenant.py --mode silent
  python update_tenant.py --mode robust --output /tmp/tenant_status.txt
"""
import argparse
import sys
import traceback

from authentik.tenants.models import Tenant


def _write(msg, output_file=None):
    if output_file:
        output_file.write(msg + "\n")
    else:
        print(msg)


def run(mode="conditional", output_path=None):
    out = None
    try:
        if output_path:
            out = open(output_path, "w")

        if mode == "conditional":
            t = Tenant.objects.first()
            _write(f"CURRENT_DOMAIN: {t.domain}", out)
            if "authentik_server" not in t.domain:
                t.domain = "authentik_server"
                t.save()
                _write("UPDATED_DOMAIN: authentik_server", out)
            else:
                _write("DOMAIN_OK", out)

        elif mode == "force":
            t = Tenant.objects.first()
            t.domain = "authentik_server"
            t.save()
            _write(f"TENANT_UPDATED: Domain='{t.domain}', Default={t.default}", out)

        elif mode == "robust":
            _write("--- LIST TENANTS ---", out)
            for t in Tenant.objects.all():
                _write(f"ID={t.pk} SCHEMA={t.schema_name} DOMAIN={t.domain} DEFAULT={t.default}", out)
            _write("--- UPDATE DEFAULT ---", out)
            t = Tenant.objects.get(default=True)
            _write(f"FOUND: {t.domain}", out)
            t.domain = "authentik_server"
            t.save()
            _write(f"UPDATED: {t.domain}", out)

        elif mode == "silent":
            # Default silent output path
            if not output_path:
                out = open("/tmp/tenant_status.txt", "w")
            _write("--- START ---", out)
            for t in Tenant.objects.all():
                _write(f"ID={t.pk} DOMAIN={t.domain} DEFAULT={t.default}", out)
                if t.default:
                    t.domain = "authentik_server"
                    t.save()
                    _write(f"UPDATED_DEFAULT_TO: {t.domain}", out)
            _write("--- END ---", out)
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            sys.exit(1)

    except Exception:
        traceback.print_exc()
        if output_path or mode == "silent":
            err_path = output_path or "/tmp/tenant_status.txt"
            with open(err_path.replace(".txt", "_error.txt"), "w") as ef:
                traceback.print_exc(file=ef)
    finally:
        if out:
            out.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update Authentik tenant domain")
    parser.add_argument(
        "--mode",
        choices=["conditional", "force", "robust", "silent"],
        default="conditional",
        help="Update mode (default: conditional)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write output to file instead of stdout",
    )
    args = parser.parse_args()
    run(mode=args.mode, output_path=args.output)
