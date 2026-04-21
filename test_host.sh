echo "--- TEST AUTHORIZE ---"
# Check if authorize endpoint exists (should be 200 or 302 or 405)
code_auth=$(curl -o /dev/null -s -w "%{http_code}" http://authentik_server:9000/application/o/authorize/)
echo "AUTH_CODE: $code_auth"

echo "--- TEST HOST HEADER ---"
# With correct Host
code_host=$(curl -o /dev/null -s -w "%{http_code}" -H "Host: localhost" -X POST http://authentik_server:9000/application/o/token/)
echo "GENERIC_HOST_LOC: $code_host"

code_host_slug=$(curl -o /dev/null -s -w "%{http_code}" -H "Host: localhost" -X POST http://authentik_server:9000/application/o/grafana/token/)
echo "SPECIFIC_HOST_LOC: $code_host_slug"

