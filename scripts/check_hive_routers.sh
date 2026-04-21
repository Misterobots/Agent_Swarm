#!/bin/bash
# Get detailed info for hive routers with warnings
docker exec traefik wget -qO- --header='Host: traefik' 'http://127.0.0.1:8080/api/http/routers' 2>/dev/null | python3 -c "
import sys, json
routers = json.load(sys.stdin)
for r in routers:
    name = r.get('name', '')
    if 'hive' in name:
        print(f'=== {name} ===')
        print(f'  status:      {r.get(\"status\", \"?\")}')
        print(f'  rule:        {r.get(\"rule\", \"?\")}')
        print(f'  priority:    {r.get(\"priority\", \"?\")}')
        print(f'  entryPoints: {r.get(\"entryPoints\", \"?\")}')
        print(f'  middlewares: {r.get(\"middlewares\", \"?\")}')
        print(f'  service:     {r.get(\"service\", \"?\")}')
        print(f'  tls:         {r.get(\"tls\", \"?\")}')
        if 'errors' in r:
            print(f'  errors:      {r[\"errors\"]}')
        print()
"

