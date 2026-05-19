from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict


class MCPRpcRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    method: str
    params: Dict[str, Any] = {}


class MCPRpcError(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class MCPRpcResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int | None = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPRpcError] = None


class MCPToolDescriptor(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPSkillDescriptor(BaseModel):
    name: str
    description: str
    category: str
    version: str = "1.0"
    tags: List[str] = []
    min_security_level: str = "L2_USER"
    triggers: Dict[str, Any] = {}


class MCPClientConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    mcpServers: Dict[str, Dict[str, Any]]
