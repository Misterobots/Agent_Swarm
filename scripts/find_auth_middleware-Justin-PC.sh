#!/bin/bash
for c in $(docker ps --format '{{.Names}}'); do
  labels=$(docker inspect "$c" -f '{{json .Config.Labels}}' 2>/dev/null)
  if echo "$labels" | grep -q 'middlewares.authentik'; then
    echo "FOUND in: $c"
    echo "$labels" | python3 -m json.tool 2>/dev/null | grep -i 'middlewares.authentik'
  fi
done

