
import json
import os
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel

# --- Constants ---
GOVERNANCE_DB_PATH = "/workspace/governance.json"

# --- Models ---
class RequestType(str, Enum):
    PACKAGE = "PACKAGE"          # pip install, apt install
    MODEL = "MODEL"              # Pull new model
    PERMISSION = "PERMISSION"    # Change file access
    FEATURE = "FEATURE"          # Request new feature
    GROUNDING_WEB = "GROUNDING_WEB"    # Grant internet/web grounding access
    GROUNDING_DOCS = "GROUNDING_DOCS"  # Grant document/library grounding access
    GROUNDING_FILE = "GROUNDING_FILE"  # Grant local workspace/filespace grounding access
    OTHER = "OTHER"

class RequestStatus(str, Enum):
    PENDING = "PENDING"
    ASSESSING = "ASSESSING" # Security/Architect reviewing
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class RequestItem(BaseModel):
    id: str
    type: RequestType
    description: str
    user: str
    timestamp: str
    status: RequestStatus
    assessment_notes: List[str] = []
    admin_notes: Optional[str] = None
    
    class Config:
        use_enum_values = True

# --- Manager ---
class GovernanceManager:
    def __init__(self, db_path=GOVERNANCE_DB_PATH):
        self.db_path = db_path
        self._load_db()

    def _load_db(self):
        if not os.path.exists(self.db_path):
            self.requests: Dict[str, dict] = {}
        else:
            try:
                with open(self.db_path, "r") as f:
                    self.requests = json.load(f)
            except Exception as e:
                print(f"[Governance] Error loading DB: {e}")
                self.requests = {}

    def _save_db(self):
        try:
            with open(self.db_path, "w") as f:
                json.dump(self.requests, f, indent=2)
        except Exception as e:
            print(f"[Governance] Error saving DB: {e}")

    def submit_request(self, type: RequestType, description: str, user: str = "coding_user") -> RequestItem:
        req_id = str(uuid.uuid4())[:8]
        
        # 1. Trigger Security Assessment
        from security_agent import get_security_agent
        sec_agent = get_security_agent()
        sec_assessment = sec_agent.evaluate_request(type, description)
        
        # 2. Trigger Architect Compatibility Check
        from leibniz_agent import assess_compatibility
        comp_assessment = assess_compatibility(type, description)
        
        status = RequestStatus.PENDING
        notes = [
            f"Security Assessment: {sec_assessment.content}",
            f"Technical Check: {comp_assessment}"
        ]
        
        # Auto-Approve if SAFE (for now, or maybe just mark as ASSESSED)
        # Let's keep it PENDING for Admin review unless it's very trivial, 
        # but the requirement says "Build Admin Approval Dashboard", so we usually want *some* approval.
        # However, to be helpful, let's say "SAFE" requests are PENDING (Green light), "UNSAFE" are REJECTED (Red light).
        
        if "UNSAFE" in sec_assessment.content:
            status = RequestStatus.REJECTED
        
        new_req = RequestItem(
            id=req_id,
            type=type,
            description=description,
            user=user,
            timestamp=datetime.utcnow().isoformat(),
            status=status,
            assessment_notes=notes
        )
        self.requests[req_id] = new_req.dict()
        self._save_db()
        return new_req

    def get_request(self, req_id: str) -> Optional[RequestItem]:
        data = self.requests.get(req_id)
        if data:
            return RequestItem(**data)
        return None

    def get_all_requests(self) -> List[RequestItem]:
        return [RequestItem(**data) for data in self.requests.values()]

    def update_status(self, req_id: str, status: RequestStatus, note: str = None) -> Optional[RequestItem]:
        if req_id in self.requests:
            self.requests[req_id]["status"] = status
            if note:
                self.requests[req_id].setdefault("assessment_notes", []).append(note)
            self._save_db()
            return RequestItem(**self.requests[req_id])
        return None
    
    def add_note(self, req_id: str, note: str):
        if req_id in self.requests:
            self.requests[req_id].setdefault("assessment_notes", []).append(note)
            self._save_db()

# Singleton
governance_manager = GovernanceManager()
