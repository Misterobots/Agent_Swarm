echo "--- HTTP CODES ---"
url_1="http://authentik_server:9000/application/o/token/"
code_1=$(curl -o /dev/null -s -w "%{http_code}" -X POST $url_1)
echo "GENERIC_SLASH: $code_1"

url_2="http://authentik_server:9000/application/o/grafana/token/"
code_2=$(curl -o /dev/null -s -w "%{http_code}" -X POST $url_2)
echo "SPECIFIC_SLASH: $code_2"

url_3="http://authentik_server:9000/application/o/token"
code_3=$(curl -o /dev/null -s -w "%{http_code}" -X POST $url_3)
echo "GENERIC_NOSLASH: $code_3"

url_4="http://authentik_server:9000/application/o/grafana/token"
code_4=$(curl -o /dev/null -s -w "%{http_code}" -X POST $url_4)
echo "SPECIFIC_NOSLASH: $code_4"

