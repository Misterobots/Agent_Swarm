
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
             st.image(artifact["path"], width="stretch")
             
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
    workspace = st.radio(
        "Mode", 
        ["Chat", "Media", "Coding", "Prototyping", "Control", "DevOps", "Maker Space", "Governance"],
        label_visibility="collapsed"
    )
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
            if st.button("Start Research", width="stretch"):
                st.session_state.quick_action = "Conduct research on..."
                st.rerun()
                
        with col2:
            st.markdown("""
            <div class="dashboard-card">
                <h3>🎨 Creative Studio</h3>
                <p>Generate Images & 3D Assets</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Studio", width="stretch"):
                st.session_state.quick_action = "Generate an image of..."
                st.rerun()

        with col3:
            st.markdown("""
            <div class="dashboard-card">
                <h3>🛡️ Security Audit</h3>
                <p>Scan code and infrastructure</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Run Audit", width="stretch"):
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
    # Helper Imports
    import sys, os, json
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
    from agents.specialized.image_gen import list_available_models

    # --- SIDEBAR CONTROLS ---
    with st.sidebar:
        st.markdown("### 🎛️ Tuning Station")
        
        # Dynamic Model List
        available_models = list_available_models()
        if not available_models: available_models = ["v1-5-pruned-emaonly.ckpt"]
        
        model_name = st.selectbox("Model Checkpoint", available_models)
        
        col1, col2 = st.columns(2)
        with col1:
            cfg = st.slider("CFG Scale", 1.0, 20.0, 7.0, 0.5)
        with col2:
             steps = st.slider("Steps", 1, 50, 20, 1)
             
        aspect = st.selectbox("Aspect Ratio", ["1:1 (Square)", "16:9 (Cinematic)", "9:16 (Mobile)"])
        w, h = 1024, 1024
        if "16:9" in aspect: w, h = 1344, 768
        elif "9:16" in aspect: w, h = 768, 1344
        
        st.caption(f"Resolution: {w}x{h}")
        
        with st.expander("🛠️ Advanced Settings"):
            col_a, col_b = st.columns(2)
            with col_a:
                sampler = st.selectbox("Sampler", ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"], index=0)
            with col_b:
                scheduler = st.selectbox("Scheduler", ["normal", "karras", "simple", "sgm_uniform"], index=0)
            
            seed = st.number_input("Seed (-1 = Random)", value=-1, step=1)
            
        st.divider()
        
        with st.expander("📦 Resource Manager"):
            new_model_url = st.text_input("CivitAI / HuggingFace URL")
            if st.button("Request Import"):
                st.info("Dispatcher: Validation Agent engaged (Stub). Checking compatibility...")
                time.sleep(1)
                st.success("Request Queued: Administrator approval required.")

    # --- MAIN GALLERY ---
    st.markdown("## 🎨 Asset Gallery")
    
    if st.button("🔄 Refresh Gallery"): st.rerun()

    gallery_path = "delivered_artifacts"
    if not os.path.exists(gallery_path):
        os.makedirs(gallery_path, exist_ok=True)
        
    try:
        images = [f for f in os.listdir(gallery_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        images.sort(key=lambda x: os.path.getmtime(os.path.join(gallery_path, x)), reverse=True)
        
        if not images:
             st.info("Gallery is empty. Start creating!")
        else:
            cols = st.columns(4)
            for idx, img_name in enumerate(images):
                img_path = os.path.join(gallery_path, img_name)
                
                # Load Metadata Sidecar
                meta_path = img_path + ".json"
                meta = {}
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as f:
                        meta = json.load(f)

                with cols[idx % 4]:
                    st.image(img_path, width="stretch")
                    st.caption(img_name)
                    
                    # Metadata Popover
                    if meta:
                        with st.popover("ℹ️ info"):
                            st.markdown(f"**Prompt**: {meta.get('prompt', 'N/A')}")
                            st.markdown(f"**Model**: `{meta.get('model', 'Auto')}`")
                            p = meta.get('params', {})
                            st.caption(f"CFG: {p.get('cfg')} | Steps: {p.get('steps')}")
                    
                    with open(img_path, "rb") as f:
                        st.download_button("⬇️", f, file_name=img_name, key=f"dl_gal_{idx}")
                        
    except Exception as e:
        st.error(f"Gallery Error: {e}")

    # --- CHAT OVERLAY ---
    st.markdown("---")
    st.markdown("### 💬 Creative Director")
    
    with st.form(key="media_chat_form", clear_on_submit=True):
        cols = st.columns([8, 1])
        with cols[0]:
            user_input = st.text_input("Describe your vision...", placeholder="A cyberpunk city in rain...", label_visibility="collapsed")
        with cols[1]:
            submit_button = st.form_submit_button("🎨 Make")
            
    if submit_button and user_input:
        # Explicit Instruction for the Agent logic
        system_directive = f"""
        User Request: {user_input}
        SYSTEM OVERRIDE: Call generate_image with:
        - model_name='{model_name}'
        - cfg={cfg}
        - steps={steps}
        - width={w}
        - height={h}
        - sampler='{sampler}'
        - scheduler='{scheduler}'
        - seed={seed if seed != -1 else 'None'}
        """
        
        with st.status("🎨 Creative Studio Active", expanded=True) as status:
            st.write(f"Sending Task: {user_input}")
            
            # BYPASS ROUTER: Direct Agent Call (v2.0)
            from agents.specialized.image_gen import get_image_gen_agent
            agent = get_image_gen_agent()
            
            try:
                response = agent.run(system_directive)
                st.write(response.content)
                
                # Check for "Generated Image" in content (tool output usually injected)
                # Since tool output implies success, we assume good.
                status.update(label="Generation Complete", state="complete", expanded=False)
                time.sleep(1) # Allow fs sync
                st.rerun()
            except Exception as e:
                status.error(f"Agent Error: {e}")

def render_ide(root_dir_param, mode="coding"):
    """
    Renders the VS Code Server via IFrame.
    - root_dir_param: The subpath to open (e.g., 'workspace/user_projects').
    """
    st.markdown(f"## 🛠️ {mode.title()} IDE (VS Code)")
    
    # URL Construction
    # We assume code-server is running on localhost:8443
    # The folder param tells code-server which directory to load.
    # Note: Inside the container, the volume is mounted at /config/workspace
    
    # Map the relative path to the container path
    # Host: ./workspace/user_projects -> Container: /config/workspace/workspace/user_projects
    
    # Map the relative path to the container path
    # Host: ./workspace/user_projects -> Container: /config/workspace (In coding container)
    # Host: ./ -> Container: /config/workspace (In devops container)
    
    if mode == "coding":
        # Coding Container (Port 8444)
        base_url = "http://localhost:8444"
        folder_path = "/config/workspace" # Root of the user_projects mount
        st.info("💡 **Tip**: This is the Restricted Coding Environment. Password is 'password'.")
    else:
        # DevOps Container (Port 8443)
        base_url = "http://localhost:8443"
        folder_path = "/config/workspace"
        st.warning("⚠️ **Root Access**: You are editing the entire system configuration.")

    final_url = f"{base_url}/?folder={folder_path}"
    
    # --- CSS: Remove Padding for Full-Screen Feel ---
    st.markdown("""
        <style>
            .block-container {
                padding-top: 1rem !important;
                padding-bottom: 0rem !important;
                padding-left: 0rem !important;
                padding-right: 0rem !important;
                max-width: 100% !important;
            }
            [data-testid="stSidebar"] {
                min-width: 350px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Imports
    try:
        from router import chat_swarm
    except ImportError:
        st.error("Router unavailable")
        return

    # --- 1. SIDEBAR (Navigation Only) ---
    with st.sidebar:
        st.markdown(f"### 📂 {mode.title()} Workspace")
        if mode == "devops":
            if st.button("🔄 Restart Stack", type="primary"):
                 st.toast("Restarting...")
        else:
            st.caption("Environment: Jailed")

    # --- 2. MAIN AREA: VS Code Iframe (Full Width) ---
    # No columns, just direct iframe to take 100% width
    import streamlit.components.v1 as components
    # Height 90vh to fill screen
    components.iframe(final_url, height=900, scrolling=True)

def render_coding_workspace():
    # Only show user projects
    render_ide("user_projects", mode="coding")

def render_devops_workspace():
    # Show everything
    render_ide(".", mode="devops")


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
            st.session_state.proto_msgs.append({"role": "user", "content": prompt})
            st.rerun()
            # In real impl, we'd call the LLM here with system_prompt

def render_governance_workspace():
    st.subheader("⚖️ Governance & Approval Dashboard")
    
    # Fetch Requests from Runtime
    import requests
    try:
        # Internal Docker Network Call
        resp = requests.get("http://agent-runtime:8000/api/v1/request", timeout=2)
        if resp.status_code == 200:
            reqs = resp.json()
        else:
            st.error(f"API Error: {resp.status_code}")
            reqs = []
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        reqs = []
        
    if not reqs:
        st.info("No active requests found.")
        return

    # Metrics
    pending = len([r for r in reqs if r['status'] == 'PENDING'])
    rejected = len([r for r in reqs if r['status'] == 'REJECTED'])
    approved = len([r for r in reqs if r['status'] == 'APPROVED'])
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Pending Review", pending)
    c2.metric("Approved", approved)
    c3.metric("Rejected", rejected)
    
    st.markdown("### Request Queue")
    
    for r in reqs:
        # Card Style
        with st.container():
            # Color Code Border
            status = r['status']
            color = "#ffd700" # Pending Yellow
            if status == "APPROVED": color = "#00ff00"
            elif status == "REJECTED": color = "#ff0000"
            
            st.markdown(f"""
            <div style="border-left: 5px solid {color}; padding-left: 10px; margin-bottom: 5px; background: rgba(255,255,255,0.05); border-radius: 5px 5px 0 0;">
                <h4 style="margin:0; padding-top:10px;">{r['type']} Request</h4>
                <p style="margin:0; padding-bottom:10px; opacity: 0.8;"><b>User:</b> {r['user']} | <b>ID:</b> {r['id']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("📝 Request Details", expanded=False):
                # 1. Metadata / Context
                c_meta1, c_meta2 = st.columns(2)
                c_meta1.text_input("Triggered By", value=r.get('user', 'Unknown'), disabled=True, key=f"u_{r['id']}")
                c_meta2.text_input("Timestamp", value=r.get('timestamp', 'N/A'), disabled=True, key=f"t_{r['id']}")
                
                st.markdown("#### Command / Payload")
                st.code(r['description'], language="text")
                
                # 2. Evaluations (Parse logic)
                sec_eval = "Pending Assessment"
                tech_eval = "Pending Assessment"
                
                if r.get("assessment_notes"):
                    for note in r["assessment_notes"]:
                        if "Security Assessment:" in note:
                            sec_eval = note.replace("Security Assessment:", "").strip()
                        elif "Technical Check:" in note:
                            tech_eval = note.replace("Technical Check:", "").strip()
                
                tab_sec, tab_tech = st.tabs(["🛡️ Security Evaluator", "🤖 Technical Architect"])
                
                with tab_sec:
                    if "UNSAFE" in sec_eval:
                        st.error(sec_eval)
                    elif "SAFE" in sec_eval:
                        st.success(sec_eval)
                    else:
                        st.info(sec_eval)
                        
                with tab_tech:
                    if "WARNING" in tech_eval:
                        st.warning(tech_eval)
                    elif "COMPATIBLE" in tech_eval:
                        st.success(tech_eval)
                    else:
                        st.info(tech_eval)
            
            # Actions (Only for Pending)
            if status == "PENDING":
                c_yes, c_no = st.columns([1, 1])
                with c_yes:
                    if st.button("✅ Approve", key=f"app_{r['id']}"):
                        try:
                            requests.post(f"http://agent-runtime:8000/api/v1/request/{r['id']}/status", json={"status": "APPROVED", "note": "Admin Approved via Dashboard"})
                            st.success("Approved!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with c_no:
                    if st.button("❌ Reject", key=f"rej_{r['id']}"):
                        try:
                            requests.post(f"http://agent-runtime:8000/api/v1/request/{r['id']}/status", json={"status": "REJECTED", "note": "Admin Rejected via Dashboard"})
                            st.warning("Rejected!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            else:
                st.caption(f"Status: {status}")
            
            st.divider()

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
        
        # --- IDENTITY CARD RENDERING (MAESTRO L7) ---
        from agents.registry import registry
        card = registry.get_card(target)
        
        col_card, col_logs = st.columns([1, 2])
        
        with col_card:
            if card:
                # Badge Color Logic
                badge_bg = "#ff4b4b" if "L3" in card.security_level or "L4" in card.security_level else "#00cc00"
                
                st.markdown(f"""
                <div style="background-color: #1e1e2e; border: 1px solid #444; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                        <span style="font-size: 1.2em; font-weight: bold; color: #fff;">🪪 {card.name}</span>
                        <span style="background-color: {badge_bg}; color: white; padding: 4px 8px; border-radius: 6px; font-size: 0.8em; font-weight: bold;">{card.security_level}</span>
                    </div>
                    <div style="color: #bbb; font-size: 0.9em; margin-bottom: 5px;">ROLE</div>
                    <div style="font-size: 1.1em; color: #fff; font-weight: 500; margin-bottom: 15px;">{card.role}</div>
                    
                    <div style="color: #bbb; font-size: 0.9em; margin-bottom: 5px;">DESCRIPTION</div>
                    <div style="font-size: 0.9em; color: #ddd; margin-bottom: 15px; line-height: 1.4;">{card.description}</div>
                    
                    <div style="border-top: 1px solid #333; padding-top: 10px; margin-top: 10px;">
                        <div style="color: #888; font-size: 0.8em; margin-bottom: 5px;">CAPABILITIES</div>
                         <div style="font-family: monospace; color: #00ff00; font-size: 0.8em;">{', '.join(card.capabilities)}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning(f"⚠️ Identity Card for '{target}' not found in Registry.")
        
        with col_logs:
            st.markdown(f"### 🕵️ Activity Log: {target}")
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

# --- MAKER SPACE WORKSPACE (PHASE 9) ---
def render_maker_workspace():
    st.markdown("## 🛠️ Maker & IoT Lab")
    
    # 1. Status Connection
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
    from agents.tools.iot_ops import get_states, call_service
    
    try:
        states_json = get_states()
        import json
        states = json.loads(states_json)
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        states = []
        
    # 2. Key Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    
    # Extract specific entities safely
    temp = next((s for s in states if "temp" in s["entity_id"]), None)
    studio_light = next((s for s in states if "studio" in s["entity_id"]), None)
    front_door = next((s for s in states if "lock" in s["entity_id"]), None)
    printer = next((s for s in states if "printer" in s["entity_id"]), None)
    
    with m1:
        val = f"{temp['state']}{temp['attributes'].get('unit_of_measurement', '°F')}" if temp else "--"
        st.metric("Test Bench Temp", val)
        
    with m2:
        val = studio_light['state'].upper() if studio_light else "OFF"
        st.metric("Work Light", val)
    
    with m3:
        val = front_door['state'].upper() if front_door else "UNKNOWN"
        st.metric("Facility Lock", val, delta_color="off" if val=="LOCKED" else "normal")
        
    with m4:
        val = printer['state'].upper() if printer else "IDLE"
        st.metric("3D Printer", val)
        
    st.markdown("---")
    
    # 3. Device Grid
    st.subheader("🔌 Hardware Test Bench (Live)")
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        for device in states:
            entity_id = device["entity_id"]
            name = device["attributes"].get("friendly_name", entity_id)
            state = device["state"]
            
            # Smart Card
            with st.container():
                cols = st.columns([3, 1, 1])
                cols[0].write(f"**{name}** (`{entity_id}`)")
                cols[1].caption(f"State: {state}")
                
                if "light" in entity_id or "switch" in entity_id:
                    if cols[2].button("Toggle", key=f"btn_{entity_id}"):
                        new_state = "turn_off" if state == "on" else "turn_on"
                        domain = entity_id.split(".")[0]
                        res = call_service(domain, new_state, entity_id)
                        st.toast(res)
                        time.sleep(1)
                        st.rerun()
                elif "lock" in entity_id:
                    cols[2].warning("LOCKED")
    
    with c2:
        st.info("ℹ️ **Lab Notes**")
        st.caption("Use the Console below to create devices or controlling existing ones.")
        
    st.markdown("---")

    # 4. Maker Console (Agent Interaction)
    st.subheader("💬 Maker Console")
    
    with st.form(key="maker_console"):
        col_input, col_btn = st.columns([6, 1])
        with col_input:
            maker_prompt = st.text_input("Command", placeholder="e.g., 'Simulate a blinky circuit with a red LED'", label_visibility="collapsed")
        with col_btn:
            run_maker = st.form_submit_button("🚀 Run")
            
    if run_maker and maker_prompt:
        with st.status("⚡ executing...", expanded=True) as status:
            st.write(f"Input: {maker_prompt}")
            
            # Run Swarm in-place
            try:
                # We reuse the main chat_swarm function
                for update in chat_swarm(maker_prompt):
                    if update["type"] == "status":
                        status.write(f"ℹ️ {update['content']}")
                    elif update["type"] == "response":
                        st.success(update["content"])
                    elif update["type"] == "artifact":
                        st.info(f"Generated: {update['content']['name']}")
                        
                status.update(label="Task Complete", state="complete", expanded=False)
                time.sleep(1.5)
                st.rerun() # Refresh to show new simulations or device states
            except Exception as e:
                status.error(f"Error: {e}")
    # 4. Simulation Lab (Wokwi Integration)
    st.markdown("---")
    st.subheader("🧪 Hardware Simulation Lab (Wokwi)")
    
    # Path relative to agents/ui.py -> workspace/simulations
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
    sim_dir = os.path.join(ROOT_DIR, "workspace", "simulations")
    
    if not os.path.exists(sim_dir):
        os.makedirs(sim_dir, exist_ok=True)
        
    projects = [d for d in os.listdir(sim_dir) if os.path.isdir(os.path.join(sim_dir, d))]
    
    col_sim_list, col_sim_view = st.columns([1, 3])
    
    with col_sim_list:
        selected_sim = st.radio("Select Project", projects) if projects else None
        if st.button("🔄 Refresh Labs"): st.rerun()
        
    with col_sim_view:
        if selected_sim:
            diagram_path = os.path.join(sim_dir, selected_sim, "diagram.json")
            if os.path.exists(diagram_path):
                import json
                with open(diagram_path, "r") as f:
                    diagram_content = f.read()

                # Robust JSON serialization
                try:
                    json_obj = json.loads(diagram_content)
                    safe_json_str = json.dumps(json_obj)
                except:
                    safe_json_str = "{}"
                    
                # Load Template
                template_path = os.path.join(os.path.dirname(__file__), "templates", "wokwi_circuit.html")
                with open(template_path, "r") as f:
                    html_template = f.read()
                    
                # Inject Data
                rendered_html = html_template.replace("{{DIAGRAM_JSON}}", safe_json_str).replace("{{PROJECT_NAME}}", selected_sim)
                
                # --- TABS FOR VIEWING MODES ---
                tab_board, tab_graph, tab_json = st.tabs(["🧩 Visual Board", "🕸️ Topology", "📜 JSON Source"])
                
                with tab_board:
                    st.caption("Rendering Visual Board via @wokwi/elements...")
                    # Render the HTML template which now contains the Wokwi Elements logic
                    import streamlit.components.v1 as components
                    components.html(rendered_html, height=600, scrolling=True)

                with tab_graph:
                    # --- MERMAID VISUALIZER ---
                    try:
                        data = json.loads(diagram_content)
                        parts = {p["id"]: p["type"].replace("wokwi-", "").replace("board-", "") for p in data.get("parts", [])}
                        
                        mermaid_code = "graph LR;\n"
                        # Style Nodes
                        for pid, ptype in parts.items():
                            mermaid_code += f"    {pid}[{ptype}]\n"
                        
                        # Edges
                        for conn in data.get("connections", []):
                            if len(conn) >= 2:
                                src = conn[0].replace(":", "_")
                                tgt = conn[1].replace(":", "_")
                                src_id = conn[0].split(":")[0]
                                tgt_id = conn[1].split(":")[0]
                                color = conn[2] if len(conn) > 2 else "wire"
                                mermaid_code += f"    {src_id} -- {conn[0].split(':')[1]} to {conn[1].split(':')[1]} ({color}) --> {tgt_id};\n"
                                
                        st.markdown(f"```mermaid\n{mermaid_code}\n```")
                    except Exception as e:
                        st.error(f"Graph Error: {e}")

                with tab_json:
                     st.json(json.loads(diagram_content))
                
                # Clean Path Display
                rel_disp = os.path.relpath(diagram_path, ROOT_DIR)
                st.caption(f"📍 Source: `{rel_disp}`")
            else:
                st.warning("Diagram.json not found in project.")
        else:
            st.info("No simulations found. Ask the agent to 'Simulate an ESP32'.")


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
elif st.session_state.workspace == "Maker Space":
    render_maker_workspace()
elif st.session_state.workspace == "Governance":
    render_governance_workspace()
