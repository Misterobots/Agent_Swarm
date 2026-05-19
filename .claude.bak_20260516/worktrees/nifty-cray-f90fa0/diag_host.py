import requests
url = "http://authentik_server:9000/-/health/ready/"
print("--- TEST HOST: authentik_server:9000 ---")
try:
    print(requests.get(url).status_code)
except Exception as e:
    print(e)

print("--- TEST HOST: localhost:9000 ---")
try:
    print(requests.get(url, headers={"Host": "localhost:9000"}).status_code)
except Exception as e:
    print(e)
