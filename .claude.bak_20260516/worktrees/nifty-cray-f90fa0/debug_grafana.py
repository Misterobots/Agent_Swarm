import subprocess

print("--- GRAFANA LOGS ---")
try:
    # key phrases to look for
    keywords = ['oauth', 'login', 'fail', 'error', '400', '401', '403', 'token']
    
    # Get logs
    result = subprocess.run(['docker', 'logs', 'grafana', '--tail', '200'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
    
    for line in result.stdout.splitlines():
        if any(x in line.lower() for x in keywords):
            print(line)
            
    for line in result.stderr.splitlines():
        if any(x in line.lower() for x in keywords):
            print(line)

except Exception as e:
    print(f"Error: {e}")
