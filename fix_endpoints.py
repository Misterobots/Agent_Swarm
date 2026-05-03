import re

# Read file with UTF-8 encoding
with open(r'C:\Users\panca\Documents\Github\Agent_Swarm\agents\main.py.backup', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace /api/v1/ with /v1/ in decorator paths only
content = re.sub(r'@app\.(get|post|put|delete)\(\"/api/v1/', r'@app.\1(\"/v1/', content)

# Write back with UTF-8 encoding
with open(r'C:\Users\panca\Documents\Github\Agent_Swarm\agents\main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('✓ Fixed endpoint paths with proper UTF-8 encoding')
