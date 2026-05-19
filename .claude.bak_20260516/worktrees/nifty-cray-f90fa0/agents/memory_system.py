import json
import os
import logging
from typing import List, Dict, Tuple

# Path to the persistent knowledge base
MEMORY_FILE = os.path.join(os.path.dirname(__file__), "skills_memory.json")
logger = logging.getLogger("MemorySystem")

class MemorySystem:
    def __init__(self):
        self.file_path = MEMORY_FILE
        self._ensure_memory_exists()

    def _ensure_memory_exists(self):
        if not os.path.exists(self.file_path):
            initial_data = {
                "visual_rules": {},  # For Art Director: "cyberpunk": ["neon", "rain"]
                "coding_rules": {},  # For Architect: "python": ["use type hints"]
                "general_rules": {}  # Universal: "tone": ["be concise"]
            }
            with open(self.file_path, 'w') as f:
                json.dump(initial_data, f, indent=4)

    def _load_memory(self) -> Dict:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            return {"visual_rules": {}, "coding_rules": {}, "general_rules": {}}

    def _save_memory(self, data: Dict):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save memory: {e}")

    def add_rule(self, domain: str, keyword: str, rule: str) -> str:
        """
        Adds a new rule to the knowledge base.
        domain: 'visual_rules', 'coding_rules', or 'general_rules'
        keyword: The trigger word (e.g., 'cyberpunk', 'python')
        rule: The instruction to remember.
        """
        data = self._load_memory()
        
        if domain not in data:
            data[domain] = {}
        
        keyword = keyword.lower().strip()
        if keyword not in data[domain]:
            data[domain][keyword] = []
        
        if rule not in data[domain][keyword]:
            data[domain][keyword].append(rule)
            self._save_memory(data)
            return f"Learned new rule for '{keyword}' in {domain}: {rule}"
        
        return f"I already know that rule for '{keyword}'."

    def get_relevant_rules(self, prompt: str, domain: str) -> List[str]:
        """
        Scans the prompt for keywords and returns all matching rules for the domain.
        """
        data = self._load_memory()
        rules = []
        
        category = data.get(domain, {})
        prompt_lower = prompt.lower()
        
        for keyword, instructions in category.items():
            # Check if keyword is in the prompt (simple containment for now)
            # Could be upgraded to embedding search later
            if keyword in prompt_lower:
                rules.extend(instructions)
                
        # Also always include 'general_rules' if they exist? 
        # For now, keep domains strict.
        
        return list(set(rules)) # Deduplicate

    def get_all_rules(self) -> Dict:
        return self._load_memory()

    def add_session_summary(self, date_key: str, topic: str, summary: str, owner_id: str | None = None) -> str:
        """
        Persists a short summary of a completed conversation under session_summaries.
        Keeps the 20 most recent entries.
        """
        data = self._load_memory()
        if "session_summaries" not in data:
            data["session_summaries"] = []
        entry = {"date": date_key, "topic": topic, "summary": summary, "owner_id": owner_id}
        data["session_summaries"].insert(0, entry)
        data["session_summaries"] = data["session_summaries"][:20]
        self._save_memory(data)
        if owner_id:
            return f"Session summary saved for {date_key} (owner={owner_id})."
        return f"Session summary saved for {date_key}."

    def get_recent_summaries(self, n: int = 5, owner_id: str | None = None) -> List[Dict]:
        """Return the N most recent session summaries, optionally filtered by owner."""
        data = self._load_memory()
        summaries = data.get("session_summaries", [])
        if owner_id:
            summaries = [entry for entry in summaries if entry.get("owner_id") == owner_id]
        return summaries[:n]

# precise singleton for import
memory = MemorySystem()
