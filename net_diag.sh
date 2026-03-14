echo "--- RESOLVE ---"
getent hosts authentik_server

echo "\n--- PING ---"
ping -c 2 authentik_server

echo "\n--- CURL ROOT ---"
curl -v http://authentik_server:9000/

echo "\n--- CURL TOKEN ---"
curl -v -X POST http://authentik_server:9000/application/o/grafana/token/ -d "grant_type=client_credentials"
