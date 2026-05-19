import subprocess

def check_logs(container):
    print(f"--- CHECKING {container} ---")
    try:
        # Get last 200 lines
        result = subprocess.run(['docker', 'logs', container, '--tail', '200'], capture_output=True, text=True, encoding='utf-8', errors='ignore')
        for line in result.stdout.splitlines():
            if any(x in line.lower() for x in ['token', 'error', 'fail', '400', '401', '403']):
                print(line)
        for line in result.stderr.splitlines():
             if any(x in line.lower() for x in ['token', 'error', 'fail', '400', '401', '403']):
                print(line)
    except Exception as e:
        print(f"Error: {e}")

check_logs('authentik_server')
check_logs('grafana')
