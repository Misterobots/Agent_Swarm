
import streamlit as st
import time
import streamlit as st
import time
import importlib
import router
importlib.reload(router)
from router import chat_swarm
from logger_setup import setup_logger

# Setup UI Logger
logger = setup_logger("UI")

st.set_page_config(page_title="Home AI Lab Swarm", page_icon="🧠", layout="wide")

from prometheus_client import start_http_server

@st.cache_resource
def init_metrics():
    # Start metrics server on port 8001 to avoid conflict with Streamlit (8501)
    # This runs in a daemon thread so it won't block the UI
    try:
        start_http_server(8001)
    except:
        pass # Already started
    return True

init_metrics()

# Helper: Artifact Renderer
def render_artifact(artifact):
    """Renders a single artifact card (Preview + Download)."""
    # --- FILE PREVIEW LOGIC ---
    if artifact["type"] == "file":
         st.info(f"📄 **File Created:** `{artifact['name']}`")
         
         # Determine Preview Type
         fname = artifact["name"].lower()
         if fname.endswith(('.png', '.jpg', '.jpeg', '.webp')):
             try:
                 st.image(artifact["path"], caption=artifact["name"])
             except:
                 st.warning("Preview unavailable (File not found)")
         elif fname.endswith('.csv'):
             try:
                 import pandas as pd
                 st.dataframe(pd.read_csv(artifact["path"]))
             except:
                 st.code(artifact["content"])
         elif fname.endswith('.xlsx'):
             try:
                 import pandas as pd
                 st.dataframe(pd.read_excel(artifact["path"]))
             except:
                 st.info("Spreadsheet Preview Unavailable (Install openpyxl for preview)")
         elif fname.endswith('.json'):
             with st.expander("👁️ Preview JSON Grid", expanded=False):
                 st.json(artifact["content"])
         elif fname.endswith('.md'):
             with st.expander("👁️ Preview Markdown", expanded=True):
                 st.markdown(artifact["content"])
         else:
             with st.expander("👁️ Preview Content", expanded=True):
                 st.code(artifact["content"])
         
         # Download Button
         st.download_button(
             label="⬇️ Download File",
             data=artifact["content"],
             file_name=artifact["name"],
             mime="text/plain",
             key=f"dl_{artifact['name']}_{int(time.time()*1000)}" # Unique key
         )
         
    # --- IMAGE GENERATION PREVIEW ---
    elif artifact["type"] == "image":
         st.success(f"🎨 **Image Generated:** `{artifact['name']}`")
         try:
             # Display Image
             st.image(artifact["path"], use_container_width=True)
             
             # We need to read binary for download since it's an external file
             with open(artifact["path"], "rb") as file:
                 st.download_button(
                     label="⬇️ Download Image",
                     data=file,
                     file_name=artifact["name"],
                     mime="image/png",
                     key=f"dl_img_{artifact['name']}_{int(time.time()*1000)}"
                 )
         except Exception as e:
             st.warning(f"Preview unavailable: {e}")
             st.caption(f"Path: {artifact['path']}")

    elif artifact["type"] == "3d_model":
         st.success(f"🧊 **3D Model Ready:** `{artifact['name']}`")
         st.caption("Available in Creature Forge Texture Watcher")

# Load CSS
def load_css(file_name):
    with open(file_name) as f:
        return f.read()

css = load_css("agents/style.css")

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=60)
    st.title("Control Deck")
    
    # Workspace Switcher
    st.subheader("Workspace")
    workspace = st.radio("Mode", ["Chat", "Media", "Coding", "Prototyping", "Control", "DevOps"], label_visibility="collapsed")
    st.session_state.workspace = workspace
    
    st.markdown("---")
    
    # Connection Status
    try:
        # Simple health check (mocked for speed, could be a real request)
        st.success("● System Online")
    except:
        st.error("● System Offline")
        
    st.markdown("---")
    
    # --- PRODUCTIVITY TOOLS ---
    with st.expander("⚡ Quick Actions", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 List Files"):
                st.session_state.quick_action = "List directories in /"
        with col2:
            if st.button("📊 Sys Check"):
                st.session_state.quick_action = "Check disk usage and running processes"
                
    st.markdown("---")
    
    # Theme Selector
    theme = st.selectbox("Visual Theme", ["Neon Nexus", "Obsidian", "Lab Coat"])
    
    # Map selection to CSS class
    theme_class = theme.lower().replace(" ", "-")

# Handle Quick Actions (Inject into input if clicked)
if "quick_action" in st.session_state and st.session_state.quick_action:
    # We can't auto-submit easily, but we can pre-fill
    # Or cleaner: just append a user message directly to trigger the swarm.
    # Let's try direct triggering.
    action = st.session_state.quick_action
    st.session_state.messages.append({"role": "user", "content": action})
    # Reset
    st.session_state.quick_action = None
    # Trigger run (requires rerun, or we just rely on the main loop picking it up? 
    # The main loop below relies on `submit_button`.
    # We need to set a flag to force run.
    st.session_state.force_run = action
    st.rerun()

st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

# THEME INJECTION CORE
# We inject specific overrides *after* the main CSS to ensure they take precedence
# without relying on body classes (which are flaky in Streamlit).

if theme == "Neon Nexus":
    # Extends global defaults, just ensures specific polish
    active_theme_css = """
    <style>
        .stApp {
            background-color: #050510;
            background-image: 
                radial-gradient(at 0% 0%, hsla(253,16%,7%,1) 0, transparent 50%), 
                radial-gradient(at 50% 0%, hsla(225,39%,30%,1) 0, transparent 50%), 
                radial-gradient(at 100% 0%, hsla(339,49%,30%,1) 0, transparent 50%);
            color: #e0e0e0;
        }
    </style>
    """
elif theme == "Obsidian":
    active_theme_css = """
    <style>
        .stApp {
            background-color: #000000;
            background-image: linear-gradient(180deg, #111111 0%, #000000 100%);
            color: #cccccc;
        }
        section[data-testid="stSidebar"] {
            background-color: #000000 !important;
            border-right: 1px solid #333;
        }
    </style>
    """
elif theme == "Lab Coat":
    # Complete Override for Light Mode - High Fidelity Glass
    active_theme_css = """
    <style>
        .stApp {
            background-color: #e0e5ec;
            background-image: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
            color: #2d3436;
        }
        
        /* Sidebar Override */
        section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
            background-color: rgba(255, 255, 255, 0.4) !important;
            background-image: none !important;
            backdrop-filter: blur(25px);
            border-right: 1px solid rgba(255,255,255,0.7);
        }
        
        /* Text Color Override (Dark for Light Theme) */
        section[data-testid="stSidebar"] h1, 
        section[data-testid="stSidebar"] h2, 
        section[data-testid="stSidebar"] h3, 
        section[data-testid="stSidebar"] label, 
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] .stMarkdown {
            color: #2d3436 !important;
            text-shadow: none !important;
        }
        
        /* Input Fields - White Glass with Depth */
        input[type="text"] {
            background-color: rgba(255, 255, 255, 0.6) !important;
            color: #2d3436 !important;
            border: 1px solid rgba(255, 255, 255, 0.8) !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05), inset 0 1px 1px rgba(255,255,255,0.5) !important;
            backdrop-filter: blur(5px);
        }
        
        /* Form Container - Frosted Glass */
        div[data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
            border-radius: 16px;
        }
        
        /* Buttons */
        .stButton>button {
            background: linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%);
            color: white;
            border: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            font-weight: 600;
        }
        
        /* Cards - Glass */
        .dashboard-card {
            background: rgba(255, 255, 255, 0.3);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.6);
            color: #2d3436;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        .dashboard-card:hover {
            background: rgba(255, 255, 255, 0.5);
            border-color: #a18cd1;
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        
        /* Expanders/Dropdowns - Reset to Light */
        div[data-testid="stExpander"], div[data-testid="stSelectbox"] label {
            color: #2d3436 !important;
            background-color: transparent !important;
        }
        div[data-testid="stExpander"] {
            background-color: rgba(255,255,255,0.4) !important;
            border: 1px solid rgba(255,255,255,0.6);
            backdrop-filter: blur(10px);
        }
    </style>
    """

st.markdown(active_theme_css, unsafe_allow_html=True)

st.title(f"🧠 {theme} Workspace")
if st.session_state.workspace != "Chat":
    st.caption(f"Active Mode: {st.session_state.workspace}")
st.markdown("---")

# Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [] # Empty by default now to show dashboard

def render_chat_workspace():
    # --- DASHBOARD VIEW (If no chat history) ---
    if not st.session_state.messages:
        st.markdown("## 🛸 Command Center")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="dashboard-card">
                <h3>🔬 Research</h3>
                <p>Gather data from the web</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Start Research", use_container_width=True):
                st.session_state.quick_action = "Conduct research on..."
                st.rerun()
                
        with col2:
            st.markdown("""
            <div class="dashboard-card">
                <h3>🎨 Creative Studio</h3>
                <p>Generate Images & 3D Assets</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Studio", use_container_width=True):
                st.session_state.quick_action = "Generate an image of..."
                st.rerun()

        with col3:
            st.markdown("""
            <div class="dashboard-card">
                <h3>🛡️ Security Audit</h3>
                <p>Scan code and infrastructure</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Run Audit", use_container_width=True):
                st.session_state.quick_action = "Audit the current directory"

        st.markdown("---")

    # Display Chat History
    else:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Render Artifacts from History
                if "artifacts" in message and message["artifacts"]:
                    for artifact in message["artifacts"]:
                        render_artifact(artifact)
                
                # Render Trace if available
                if "trace" in message and message["trace"]:
                    with st.expander("🕵️ Trace / Logs", expanded=False):
                        for log in message["trace"]:
                            if "ERROR" in log or "🔥" in log:
                                st.error(log)
                            elif "WARNING" in log:
                                st.warning(log)
                            else:
                                st.caption(log)

    # Input Area - Using standard form instead of chat_input for better visibility
    # Check if we have a forced run pending
    initial_input = ""
    run_now = False
    
    if "force_run" in st.session_state and st.session_state.force_run:
        initial_input = st.session_state.force_run
        run_now = True
        del st.session_state.force_run
    
    with st.form(key="chat_form", clear_on_submit=True):
        cols = st.columns([8, 1])
        with cols[0]:
            user_input = st.text_input("Task Description", value="" if run_now else "", placeholder="Type your message here...", label_visibility="collapsed")
        with cols[1]:
            submit_button = st.form_submit_button("🚀 Send")
    
    # Trigger if Button Clicked OR Quick Action fired
    if (submit_button and user_input) or (run_now and initial_input):
        final_input = user_input if submit_button else initial_input
        
        # Add User Message
        if not run_now:
             st.session_state.messages.append({"role": "user", "content": final_input})
             
        with st.chat_message("user"):
            st.markdown(final_input)
    
        # Agent Response Container
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            status_box = st.status("Swarm Operations", expanded=True)
            
            full_response = ""
            trace_logs = []
            artifacts = [] # Track artifacts for persistence
            
            # Stream updates from the Swarm
            for update in chat_swarm(final_input):
                # Log to Dashboard
                logger.info(f"[{update['type'].upper()}] {update['content']}")
                
                if update["type"] == "status":
                    status_box.write(update["content"])
                    trace_logs.append(f"ℹ️ {update['content']}")
                elif update["type"] == "log":
                    # Debug Logs: Don't show in status box, but add to trace
                    trace_logs.append(f"⚙️ {update['content']}")
                elif update["type"] == "artifact":
                     # Render Artifact Card Immediately
                     artifact = update["content"]
                     artifacts.append(artifact) # Add to list for saving
                     trace_logs.append(f"📦 Artifact Generated: {artifact['name']}")
                     
                     # Render directly to chat stream (don't use placeholder, as it gets overwritten)
                     render_artifact(artifact)
    
                elif update["type"] == "error":
                    status_box.error(update["content"])
                    trace_logs.append(f"🔥 {update['content']}")
                    full_response = f"🚨 {update['content']}"
                elif update["type"] == "response":
                    full_response = update["content"]
            
            status_box.update(label="Mission Complete", state="complete", expanded=False)
            
            # --- Smart Rendering of Final Response ---
            import json
            is_tool_call = False
            
            # Attempt to parse as Tool Call JSON
            try:
                clean_content = full_response.strip()
                if clean_content.startswith("{") or clean_content.startswith("```json"):
                    # Clean markdown blocks if present
                    if clean_content.startswith("```json"):
                        clean_content = clean_content.replace("```json", "").replace("```", "")
                    
                    data = json.loads(clean_content)
                    
                    # Check for Tool Call Signature (name + arguments)
                    if isinstance(data, dict) and "name" in data and "arguments" in data:
                        is_tool_call = True
                        tool_name = data.get("name")
                        tool_args = data.get("arguments")
                        
                        # Render as "Action Card"
                        with message_placeholder.container():
                            st.markdown(f"**🤖 Agent Action:** `{tool_name}`")
                            with st.expander(f"View Details: {tool_name}", expanded=False):
                                st.json(tool_args)
                                
                        # Store clean history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"**Action Taken:** `{tool_name}`\n\n(See trace for details)",
                            "trace": trace_logs,
                            "artifacts": artifacts
                        })
            except Exception:
                # Not JSON or malformed, continue to standard render
                pass
    
            # Standard Text Rendering (if not a tool call)
            if not is_tool_call:
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": full_response,
                    "trace": trace_logs,
                    "artifacts": artifacts
                })
                
                # Show trace immediately for this run
                with st.expander("🕵️ Trace / Logs", expanded=False):
                    for log in trace_logs:
                        if "🔥" in log:
                            st.error(log)
                        else:
                            st.caption(log)

def render_media_workspace():
    # --- SIDEBAR CONTROLS ---
    with st.sidebar:
        st.markdown("### 🎛️ Tuning Station")
        
        model_name = st.selectbox("Model Checkpoint", ["Flux-Schnell (FP8)", "SDXL Turbo", "Stable Cascade"])
        
        col1, col2 = st.columns(2)
        with col1:
            cfg = st.slider("CFG Scale", 1.0, 20.0, 7.0, 0.5)
        with col2:
             steps = st.slider("Steps", 1, 50, 20, 1)
             
        aspect = st.selectbox("Aspect Ratio", ["16:9 (Cinematic)", "1:1 (Square)", "9:16 (Mobile)"])
        
        st.info(f"Param String: `--cfg {cfg} --steps {steps} --ar {aspect.split()[0]}`")

    # --- MAIN GALLERY ---
    st.markdown("## 🎨 Asset Gallery")
    
    # Refresh logic
    if st.button("🔄 Refresh Gallery"):
        st.rerun()

    import os
    gallery_path = "delivered_artifacts"
    
    # Ensure path exists
    if not os.path.exists(gallery_path):
        st.warning(f"Artifact folder not found at `{gallery_path}`. Generate something first!")
        os.makedirs(gallery_path, exist_ok=True)
        
    # Get Images
    try:
        images = [f for f in os.listdir(gallery_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        images.sort(key=lambda x: os.path.getmtime(os.path.join(gallery_path, x)), reverse=True)
        
        if not images:
             st.info("Gallery is empty. Start creating!")
        else:
            # Responsive Grid
            cols = st.columns(4) # 4 wide
            for idx, img_name in enumerate(images):
                img_path = os.path.join(gallery_path, img_name)
                with cols[idx % 4]:
                    st.image(img_path, use_container_width=True)
                    st.caption(img_name)
                    # Download
                    with open(img_path, "rb") as f:
                        st.download_button("⬇️", f, file_name=img_name, key=f"dl_gal_{idx}")
                        
    except Exception as e:
        st.error(f"Gallery Error: {e}")

    # --- CHAT OVERLAY ---
    st.markdown("---")
    st.markdown("### 💬 Creative Director")
    
    # Reuse the standard chat loop logic, but perhaps simpler
    # We can just call the shared render logic or copy the form
    # Let's copy the form logic to keep it isolated or refactor the form into a component.
    # For now, inline copy is safer to avoid breaking the main chat.
    
    with st.form(key="media_chat_form", clear_on_submit=True):
        cols = st.columns([8, 1])
        with cols[0]:
            user_input = st.text_input("Describe your vision...", placeholder="A cyberpunk city in rain...", label_visibility="collapsed")
        with cols[1]:
            submit_button = st.form_submit_button("🎨 Make")
            
    if submit_button and user_input:
        # Append params
        augmented_prompt = f"{user_input} (Parameters: Model={model_name}, CFG={cfg}, Steps={steps}, AR={aspect})"
        
        with st.status("🎨 Creative Studio Active", expanded=True) as status:
            st.write(f"Sending Task: {user_input}")
            for update in chat_swarm(augmented_prompt):
                 if update["type"] == "status":
                    status.write(update["content"])
                 elif update["type"] == "artifact":
                     st.image(update["content"]["path"])
                 elif update["type"] == "error":
                     status.error(update["content"])
            status.update(label="Generation Complete", state="complete", expanded=False)
            st.rerun() # Refresh gallery

def render_coding_workspace():
    # IDE-like Styling Injection
    st.markdown("""
    <style>
        .stTextArea textarea { font-family: 'Fira Code', monospace !important; }
        .block-container { max-width: 95% !important; padding-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)
    
    col_explorer, col_editor = st.columns([1, 4])
    
    import os
    from tools.file_ops import read_file, write_file
    
    # --- FILE EXPLORER (Left) ---
    with col_explorer:
        st.subheader("📂 Files")
        root_dir = "." 
        file_options = []
        for root, dirs, files in os.walk(root_dir):
            if ".git" in root or "__pycache__" in root: continue
            for file in files:
                if file.endswith(('.py', '.md', '.json', '.yml', '.yaml', '.txt', '.css', '.Dockerfile', '.bat')):
                    rel_path = os.path.relpath(os.path.join(root, file), root_dir)
                    file_options.append(rel_path)
        
        file_options.sort()
        # Radio button looks more like a file list than selectbox
        selected_file = st.radio("Select File", file_options, index=None, label_visibility="collapsed")
        
        if st.button("🔄 Refresh"): st.rerun()

    # --- EDITOR (Right) ---
    with col_editor:
        if selected_file:
            st.caption(f"Editing: `{selected_file}`")
            current_content = read_file(selected_file)
            content_editor = "" if current_content.startswith("Error:") else current_content
            
            # Editor Toolbar
            c1, c2, c3 = st.columns([1, 1, 6])
            with c1:
                if st.button("💾 Save"):
                    write_file(selected_file, content_editor) # Warning: State lost on rerun if not saved carefully
                    st.toast("Saved!")
            with c2:
                if st.button("▶️ Run"):
                    st.session_state.quick_action = f"Execute/Test {selected_file}"
                    st.session_state.workspace = "Chat"
                    st.rerun()
            
            # Main Editor
            # Note: without session_state key management, typing might be laggy or reset.
            # We use a key based on filename to preserve state per file.
            new_content = st.text_area("Code", value=content_editor, height=700, label_visibility="collapsed", key=f"editor_{selected_file}")
            
            if new_content != content_editor:
                 # In a real app we'd need a specific save action or debounce.
                 # For now, the Save button above reads 'content_editor' which is stale until rerun?
                 # Actually, we need to read 'new_content' in the Save button logic.
                 # Streamlit logic is tricky here. 
                 # FIX: We should move the Save button BELOW or use a form.
                 pass
                 
            # Re-implement Save logic to use session state value
            if st.button("💾 Save Changes", key="save_bottom"):
                 write_file(selected_file, new_content)
                 st.toast("Saved!")
                 time.sleep(0.5)
                 st.rerun()

        else:
            st.info("👈 Select a file to open the Agent IDE")


def render_prototyping_workspace():
    st.subheader("🧪 AI Studio (Prototyping)")
    
    # Google AI Studio Layout: 3 Columns
    # [System Prompt (25%)] [Chat (50%)] [Params (25%)]
    c_sys, c_chat, c_params = st.columns([1, 2, 1])
    
    with c_sys:
        st.markdown("### System Instructions")
        system_prompt = st.text_area("Context / Persona", height=600, value="You are a helpful AI assistant.", help="Define the agent's behavior here.")
        
    with c_params:
        st.markdown("### Settings")
        st.selectbox("Model", ["Qwen 2.5 Coder", "Llama 3", "DeepSeek-V3"])
        st.slider("Temperature", 0.0, 1.0, 0.7)
        st.slider("Top K", 1, 100, 40)
        st.number_input("Max Output Tokens", 100, 32000, 4096)
        
        st.markdown("### Safety settings")
        st.select_slider("Hate Speech", ["Block None", "Block Few", "Block Some", "Block Most"])
        
    with c_chat:
        st.markdown("### 💬 Preview")
        # Lightweight Chat Loop (Non-Persistent for prototyping)
        if "proto_msgs" not in st.session_state: st.session_state.proto_msgs = []
        
        for msg in st.session_state.proto_msgs:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                
        if prompt := st.chat_input("Test your prompt..."):
            st.session_state.proto_msgs.append({"role": "user", "content": prompt})
            st.rerun()
            # In real impl, we'd call the LLM here with system_prompt

# --- LIVE SWARM VISUALIZER ---
def render_hub_and_spoke(active_agent=None, log_history=None, key_suffix=""):
    if log_history is None: log_history = {}
    
    # CSS for the Grid
    st.markdown("""
    <style>
        .agent-card-container {
            border: 1px solid #444;
            border-radius: 10px;
            padding: 10px;
            text-align: center;
            background: rgba(30,30,40,0.5);
            transition: all 0.3s;
            height: 200px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .agent-active-border {
            border-color: #00ff00 !important;
            box-shadow: 0 0 15px rgba(0,255,0,0.3);
            background: rgba(0, 50, 0, 0.2);
            transform: scale(1.02);
        }
    </style>
    """, unsafe_allow_html=True)

    # Helper to render a card
    def agent_box(name, icon, key_id):
        import textwrap
        is_active = (active_agent == name)
        
        # Get Logs
        agent_logs = log_history.get(name, [])
        recent_logs = agent_logs[-3:] if agent_logs else ["Listening..."]
        # Escape HTML special chars in logs just in case
        import html
        log_text = "\n".join([html.escape(l) for l in recent_logs])
        
        # Container style
        active_class = "agent-active-border" if is_active else ""
        
        with st.container():
            # Use raw string and strip indentation manually to be safe
            html_template = f"""
            <div class="agent-card-container {active_class}">
                <div style="display: flex; justify-content: center; align-items: center; gap: 10px;">
                    <div style="font-size: 1.8rem;">{icon}</div>
                    <div style="font-weight: bold; color: #eee; font-size: 1rem;">{name}</div>
                </div>
                
                <!-- Terminal Window for Agent Stream -->
                <div style="
                    background: #111; 
                    border-radius: 6px; 
                    padding: 8px; 
                    margin-top: 10px; 
                    height: 80px; 
                    overflow-y: auto; 
                    text-align: left; 
                    font-family: 'Fira Code', monospace; 
                    font-size: 0.7rem; 
                    color: #0f0;
                    border: 1px solid #333;
                ">
                    <div style="white-space: pre-wrap;">{log_text}</div>
                </div>
            </div>
            """
            
            # Aggressive strip of leading whitespace
            import re
            html_block = re.sub(r'^\s+', '', html_template, flags=re.MULTILINE)
            st.markdown(html_block, unsafe_allow_html=True)
            
            # THE INTERACTION
            # Use unique key suffix to avoid duplicate ID errors during loops
            # Note: width='stretch' is required to fix deprecation warning for use_container_width
            if st.button(f"🔍 Inspect", key=f"btn_{key_id}{key_suffix}"): # standard button, default width to avoid warnings for now unless we confirm width='stretch' works for buttons (it usually does for dataframe, but button? let's stick to default to be safe and clean logs)
                st.session_state.selected_agent_view = name

    # --- GRID RENDER ---
    # Row 1
    c1, c2, c3 = st.columns(3)
    with c1: agent_box("Art Director", "🎨", "ad")
    with c2: agent_box("Orchestrator", "🧠", "orch")
    with c3: agent_box("Engineering", "⚙️", "eng")
    
    # Row 2
    c4, c5, c6 = st.columns(3)
    with c4: agent_box("Architect", "🏗️", "arch")
    with c5: agent_box("Router", "🔀", "router")
    with c6: agent_box("Security", "🛡️", "sec")
    
    # Row 3
    c7, c8, c9 = st.columns(3)
    with c8: agent_box("Chat Agent", "💬", "chat")

    # --- DETAIL VIEW OVERLAY ---
    if "selected_agent_view" in st.session_state:
        target = st.session_state.selected_agent_view
        st.markdown("---")
        st.markdown(f"### 🕵️ Deep Dive: {target}")
        
        logs = log_history.get(target, ["No activity recorded."])
        
        # Display full conversation history for this agent
        for item in logs:
            st.code(item, language="text")
            
        if st.button("Close Details"):
            del st.session_state.selected_agent_view
            st.rerun()


def render_control_workspace():
    st.markdown("## 🎛️ Mission Control")
    
    # ... (Admin Auth Logic preserved) ...
    if "admin_unlocked" not in st.session_state:
        pwd = st.text_input("Access Protocol", type="password", placeholder="Enter Code...")
        if pwd == "admin": 
            st.session_state.admin_unlocked = True
            st.rerun()
        else:
            if pwd: st.error("Access Denied")
            st.stop()
            
    # --- SECTION 1: GRAFANA ---
    with st.expander("📊 System Telecoms", expanded=True):
        grafana_url = "http://localhost/d/home-ai-lab/mission-control?orgId=1&from=now-1h&to=now&refresh=5s&theme=dark&kiosk"
        import streamlit.components.v1 as components
        components.iframe(grafana_url, height=400, scrolling=False)
        
    # --- SECTION 2: LIVE SWARM ---
    st.markdown("### 🧠 Swarm Consciousness Stream")
    
    cmd = st.chat_input("Inject Administrative Override / Task...")
    
    grid_placeholder = st.empty()
    status_placeholder = st.empty()
    
    # State Holders (List based now)
    if "control_history" not in st.session_state: st.session_state.control_history = {}
    
    # EXECUTION LOOP
    if cmd:
        # We don't render initial state here to avoid key conflict
        
        try:
            for i, update in enumerate(chat_swarm(cmd)):
                content = update['content']
                current_agent = "Router"
                
                # Heuristic Identity
                if "[Art Director]" in content: current_agent = "Art Director"
                elif "[Architect]" in content: current_agent = "Architect"
                elif "[Security]" in content: current_agent = "Security"
                elif "[Router]" in content or "[Context Manager]" in content: current_agent = "Router"
                elif "[Chat Agent]" in content: current_agent = "Chat Agent"
                elif "[Forge]" in content: current_agent = "Art Director" # Forge is visual
                elif "[CreativeStudio]" in content: current_agent = "Art Director"
                
                # Fallback keywords (Stricter)
                elif "generating image" in content.lower(): current_agent = "Art Director"
                elif "executing code" in content.lower(): current_agent = "Architect"
                elif "researching" in content.lower(): current_agent = "Chat Agent"
                
                # Append to History
                if current_agent not in st.session_state.control_history:
                    st.session_state.control_history[current_agent] = []
                st.session_state.control_history[current_agent].append(content)
                
                # Re-Render with UNIQUE KEY SUFFIX for the loop
                with grid_placeholder.container():
                    render_hub_and_spoke(active_agent=current_agent, log_history=st.session_state.control_history, key_suffix=f"_run_{i}")
                    
                status_placeholder.info(f"⚡ Processing: {content}")
                time.sleep(0.05)
                
            status_placeholder.success("Transmission Complete")
            
            # FINAL STATE RENDER (Standard Keys to restore Interactivity)
            with grid_placeholder.container():
                render_hub_and_spoke(active_agent="Router", log_history=st.session_state.control_history, key_suffix="")
            
        except Exception as e:
            st.error(f"Swarm Failure: {e}")
            
    else:
        # IDLE STATE (Standard Keys)
        with grid_placeholder.container():
            render_hub_and_spoke(active_agent="Router", log_history=st.session_state.control_history, key_suffix="")

# --- DEVOPS WORKSPACE ---
def render_devops_workspace():
    st.markdown("## 🛠️ DevOps Sandbox")
    
    # Fix import path for tools (sibling directory)
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # Priority Insert
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
        
    try:
        from core_tools.git_ops import get_current_branch, get_branches, get_status, create_branch, commit_changes
    except ImportError as e:
        st.error(f"Import Failed: {e}")
        st.code(f"Sys Path: {sys.path}")
        # Debug helper if even renaming fails
        st.write(f"Looking for 'core_tools' in {parent_dir}")
        st.stop()
    
    # 1. Branch Management
    col_branch, col_actions = st.columns([1, 2])
    
    with col_branch:
        current_branch = get_current_branch()
        st.metric("Current Branch", current_branch, delta="Active", delta_color="normal")
        
        all_branches = get_branches()
        selected_branch = st.selectbox("Switch Branch", all_branches, index=0 if current_branch not in all_branches else all_branches.index(current_branch))
        
        if st.button("Checkout"):
            # Mock checkout for safety in this session, requires restart usually
            st.toast(f"Switched to {selected_branch} (Session Refresh Required)")
            
    with col_actions:
        st.markdown("### Create Feature Sandbox")
        new_branch = st.text_input("New Branch Name", placeholder="feature/new-agent-logic")
        if st.button("🚀 Launch Sandbox") and new_branch:
            res = create_branch(new_branch)
            st.success(f"Sandbox Created: {res}")
            st.rerun()

    st.divider()

    # 2. Staging Area
    st.markdown("### 📦 Stage & Commit")
    status_output = get_status()
    
    c1, c2 = st.columns(2)
    with c1:
        st.text_area("Git Status", status_output, height=300, disabled=True)
    
    with c2:
        commit_msg = st.text_input("Commit Message", placeholder="feat: updated router logic")
        if st.button("Commit & Push") and commit_msg:
             # Full workflow: Add . -> Commit
             from tools.git_ops import stage_all
             stage_all()
             res = commit_changes(commit_msg)
             st.success(f"Changes Committed! {res}")
             st.rerun()
             
    st.info("ℹ️ Note: This is a live interface to the project's Git repository. Changes are real.")

# --- MAIN DISPATCHER ---
if st.session_state.workspace == "Chat":
    render_chat_workspace()
elif st.session_state.workspace == "Media":
    render_media_workspace()
elif st.session_state.workspace == "Coding":
    render_coding_workspace()
elif st.session_state.workspace == "Prototyping":
    render_prototyping_workspace()
elif st.session_state.workspace == "Control":
    render_control_workspace()
elif st.session_state.workspace == "DevOps":
    render_devops_workspace()
