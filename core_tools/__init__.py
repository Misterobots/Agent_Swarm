# Expose core tools
from .git_ops import *
from .workspace_search import search_files, search_content, read_workspace_file
from .capability_guard import require_capability, set_current_agent, clear_current_agent
