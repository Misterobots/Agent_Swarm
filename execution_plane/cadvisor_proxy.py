import urllib.request
import socket
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
import os

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            try:
                config_host = os.environ.get('CADVISOR_HOST', 'cadvisor:8080')
                response = urllib.request.urlopen(f'http://{config_host}/metrics').read().decode('utf-8')
                
                # Fetch Docker ID to Name mapping directly from Unix socket
                mapping = {}
                try:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect('/var/run/docker.sock')
                    sock.sendall(b'GET /containers/json?all=1 HTTP/1.0\r\n\r\n')
                    resp_data = b''
                    while True:
                        chunk = sock.recv(4096)
                        if not chunk: break
                        resp_data += chunk
                    sock.close()
                    
                    body = resp_data.decode('utf-8').split('\r\n\r\n', 1)[1]
                    containers = json.loads(body)
                    for c in containers:
                        full_id = c['Id']
                        name = c['Names'][0].lstrip('/')
                        mapping[full_id] = name
                except Exception as e:
                    print("Docker socket error:", e)
                
                # Replace id="/docker/FULL_HASH" with id="/docker/FULL_HASH",name="CONTAINER_NAME"
                for cid, cname in mapping.items():
                    # cAdvisor can use short IDs or full IDs, typically full 64-char IDs
                    # We regex replace to gracefully append the name label
                    pattern = r'(id="/docker/' + cid + r'")'
                    replacement = r'\1,name="' + cname + r'"'
                    response = re.sub(pattern, replacement, response)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    print(f"Starting cAdvisor proxy on port {port}...")
    server = HTTPServer(('0.0.0.0', port), ProxyHTTPRequestHandler)
    server.serve_forever()
