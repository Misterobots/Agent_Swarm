echo "--- TESTING GENERIC ENDPOINT ---"
curl -v -X POST http://authentik_server:9000/application/o/token/ \
  -d "grant_type=authorization_code" \
  -d "client_id=e6xl4adDhaDNjvOGKgLfxnZlcFQ8EGadEmOIZMar"

echo "\n\n--- TESTING SPECIFIC ENDPOINT ---"
curl -v -X POST http://authentik_server:9000/application/o/grafana/token/ \
  -d "grant_type=authorization_code" \
  -d "client_id=e6xl4adDhaDNjvOGKgLfxnZlcFQ8EGadEmOIZMar"
