import unittest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.routes import router
from mcp.server import MCPBridgeServer
from mcp.schema import MCPToolDescriptor


class MCPHTTPTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_notification_has_empty_accepted_response(self):
        with patch('mcp.routes.get_mcp_server') as server:
            result = self.client.post('/api/v1/mcp/rpc', json={
                'jsonrpc': '2.0', 'method': 'notifications/initialized'})
            self.assertEqual(result.status_code, 202)
            self.assertEqual(result.content, b'')
            server.assert_not_called()

    def test_success_has_no_null_error_and_forwards_auth(self):
        with patch('mcp.routes.get_mcp_server') as server:
            server.return_value.handle_rpc = AsyncMock(return_value={'tools': []})
            result = self.client.post('/api/v1/mcp/rpc', headers={'Authorization': 'Bearer test'}, json={
                'jsonrpc': '2.0', 'id': 0, 'method': 'tools/list'})
            self.assertEqual(result.json(), {'jsonrpc': '2.0', 'id': 0, 'result': {'tools': []}})
            server.return_value.handle_rpc.assert_awaited_once_with('tools/list', {}, auth_header='Bearer test')

    def test_tool_schema_uses_protocol_spelling(self):
        server = MCPBridgeServer.__new__(MCPBridgeServer)
        server._tools = [MCPToolDescriptor(name='test', description='test', input_schema={'type': 'object'})]
        self.assertEqual(server.list_tools()[0]['inputSchema'], {'type': 'object'})
        self.assertNotIn('input_schema', server.list_tools()[0])

    def test_get_explicitly_declines_sse(self):
        self.assertEqual(self.client.get('/api/v1/mcp/rpc').status_code, 405)
