#!/usr/bin/env python3
"""Update Turing spire-agent command with join token."""
import sys

path = '/home/misterobots/Home_AI_Lab/turing_gateway/docker-compose.yml'
old = 'cbcd697f-0419-4fe4-b395-b14e623b32e1'
new = '92977ffa-9147-4f55-bc93-0654169c1c26'

with open(path) as f:
    content = f.read()

if old not in content:
    print("ERROR: old string not found")
    sys.exit(1)

content = content.replace(old, new, 1)

with open(path, 'w') as f:
    f.write(content)

print("REPLACED")


