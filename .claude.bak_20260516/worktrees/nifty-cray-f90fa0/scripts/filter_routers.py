import sys, json
routers = json.load(sys.stdin)
for r in routers:
    name = r.get('name', '')
    if 'hive' in name:
        print(f"  {name:45s}  priority={r.get('priority','?'):>3}  status={r.get('status','?')}")
