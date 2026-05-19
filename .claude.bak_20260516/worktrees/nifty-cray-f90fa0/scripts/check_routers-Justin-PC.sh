#!/bin/bash
curl -sf http://localhost:8080/api/http/routers 2>/dev/null | python3 -c "
import sys, json
routers = json.load(sys.stdin)
for r in routers:
    name = r.get('name', '')
    if 'hive' in name:
        print(f'{name:45s} P:{r.get(\"priority\",\"—\"):>3}  Rule: {r[\"rule\"][:90]}')
"

