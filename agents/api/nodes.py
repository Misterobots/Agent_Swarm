"""
Node sync and verification endpoints for Pioneer network
"""
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/nodes", tags=["nodes"])

SCRIPT_DIR = Path(__file__).parent.parent.parent / "scripts"
LOVELACE_SCRIPT_DIR = r"C:\Users\panca\Documents\Github\Agent_Swarm\scripts"

class NodeVerifyRequest(BaseModel):
    action: Literal["sync", "verify", "full"] = "verify"

class DeployRequest(BaseModel):
    component: Literal["hive-ui", "agent-runtime", "postgres", "redis", "all"]
    target: Literal["Turing", "Hopper", "All"]
    skip_checks: bool = False
    no_build: bool = False

@router.post("/verify")
async def verify_nodes(request: NodeVerifyRequest) -> Dict[str, Any]:
    """
    Run sync/verify checks on all Pioneer nodes
    """
    script_path = LOVELACE_SCRIPT_DIR / "sync-verify-nodes.ps1"
    
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"Verification script not found at {script_path}"
        )
    
    try:
        # Run PowerShell script with JSON output
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-Action", request.action
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "RETURN_JSON": "1"}
        )
        
        # Parse JSON output if available
        try:
            results = json.loads(result.stdout)
        except json.JSONDecodeError:
            results = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        
        return {
            "success": result.returncode == 0,
            "results": results,
            "action": request.action
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Verification timed out after 120 seconds"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )

@router.post("/deploy")
async def safe_deploy(request: DeployRequest) -> Dict[str, Any]:
    """
    Deploy component with pre/post validation checks
    """
    script_path = LOVELACE_SCRIPT_DIR / "safe-deploy.ps1"
    
    if not os.path.exists(script_path):
        raise HTTPException(
            status_code=500,
            detail=f"Deployment script not found at {script_path}"
        )
    
    try:
        # Build PowerShell command
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", str(script_path),
            "-Component", request.component,
            "-Target", request.target
        ]
        
        if request.skip_checks:
            cmd.append("-SkipChecks")
        if request.no_build:
            cmd.append("-NoBuild")
        
        # Run deployment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for build
        )
        
        return {
            "success": result.returncode == 0,
            "component": request.component,
            "target": request.target,
            "output": result.stdout,
            "errors": result.stderr if result.stderr else None
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Deployment timed out after 5 minutes"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deployment failed: {str(e)}"
        )

@router.get("/status")
async def node_status() -> Dict[str, Any]:
    """
    Quick status check of all nodes (lightweight)
    """
    script_path = LOVELACE_SCRIPT_DIR / "sync-verify-nodes.ps1"
    
    if not os.path.exists(script_path):
        return {
            "available": False,
            "error": "Verification script not configured"
        }
    
    try:
        # Quick verify only (no sync)
        result = subprocess.run(
            [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-Action", "verify",
                "-Quiet"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "RETURN_JSON": "1"}
        )
        
        try:
            results = json.loads(result.stdout)
        except json.JSONDecodeError:
            results = {"raw_output": result.stdout}
        
        return {
            "available": True,
            "healthy": result.returncode == 0,
            "results": results
        }
    
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }
