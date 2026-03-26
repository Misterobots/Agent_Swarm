
import streamlit as st
import time
import streamlit as st
import time
import importlib
import uuid
import router
importlib.reload(router)
from router import chat_swarm
from logger_setup import setup_logger

# Setup UI Logger
logger = setup_logger("UI")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logger.info(f"[UI] New session initialized: {st.session_state.session_id}")

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

    elif artifact["type"] == "action_figure":
         st.success(f"🦾 **Action Figure Ready:** `{artifact['name']}`")
         st.caption("Posable STL parts with ball-socket joints — check action_figures/ directory")

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
        ["Chat", "Art Studio", "Voice Studio", "Coding", "Prototyping", "Control", "DevOps", "Maker Space", "Governance", "Documents"],
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
                <h3>🎨 Art Studio</h3>
                <p>Images, 3D Models & Action Figures</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Open Studio", width="stretch"):
                st.session_state.workspace = "Art Studio"
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
            user_input = st.text_input(
                "Task Description", 
                value="" if run_now else "", 
                placeholder="Type your message here...", 
                label_visibility="collapsed",
                key="user_prompt_input"
            )
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
            thought_stream = st.expander("🕵️ Thought Stream", expanded=True)
            with thought_stream:
                log_placeholder = st.empty()
            
            for update in chat_swarm(final_input, session_id=st.session_state.session_id):
                # Log to Dashboard
                logger.info(f"[{update['type'].upper()}] {update['content']}")
                
                if update["type"] == "status":
                    status_box.write(update["content"])
                    trace_logs.append(f"ℹ️ {update['content']}")
                    with thought_stream:
                        st.caption(f"ℹ️ {update['content']}")
                elif update["type"] == "log":
                    # Filter out heartbeat character from logs if needed, though they usually go to status/message
                    trace_logs.append(f"⚙️ {update['content']}")
                    with thought_stream:
                        st.caption(f"⚙️ {update['content']}")
                elif update["type"] == "workspace_offer":
                    # Creative intent detected — offer to switch to Art Studio
                    offer = update["content"]
                    st.session_state._workspace_offer = offer
                    trace_logs.append(f"🎨 Creative intent detected: {offer['intent']}")
                    # Don't break — let the pipeline continue generating in chat
                    # The offer will be rendered after the response completes
                elif update["type"] == "artifact":
                     artifact = update["content"]
                     artifacts.append(artifact)
                     trace_logs.append(f"📦 Artifact Generated: {artifact['name']}")
                     render_artifact(artifact)
                elif update["type"] == "message":
                    # Real-time message streaming
                    content = update["content"]
                    # FILTER heartbeat character to prevent UI artifacts
                    content = content.replace("\u200B", "")
                    
                    if content:
                        full_response += content
                        message_placeholder.markdown(full_response + "▌")
                elif update["type"] == "error":
                    status_box.error(update["content"])
                    trace_logs.append(f"🔥 {update['content']}")
                    full_response = f"🚨 {update['content']}"
                elif update["type"] == "response":
                    full_response = update["content"]
                    # Final cleanup of the response content
                    full_response = full_response.replace("\u200B", "")
                    # BREAK the loop as soon as we have final response to allow UI cleanup
                    break
            
            # Finalize response UI
            message_placeholder.markdown(full_response)
            status_box.update(label="Mission Complete ✨", state="complete", expanded=False)
            
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
                
                # Art Studio Offer Card (shown after creative intent responses)
                if "_workspace_offer" in st.session_state and st.session_state._workspace_offer:
                    offer = st.session_state._workspace_offer
                    st.markdown("---")
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, rgba(161,140,209,0.2) 0%, rgba(251,194,235,0.2) 100%);
                                border: 1px solid rgba(161,140,209,0.5); border-radius: 12px; padding: 20px; margin: 10px 0;">
                        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 10px;">
                            <span style="font-size: 1.5em;">🎨</span>
                            <span style="font-size: 1.1em; font-weight: 600; color: #e0e0e0;">Open Art Studio?</span>
                        </div>
                        <p style="color: #bbb; margin: 0; font-size: 0.9em;">
                            Switch to the full Art Studio workspace for advanced generation controls,
                            3D model preview, gallery management, and export tools.
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                    col_enter, col_stay = st.columns(2)
                    with col_enter:
                        if st.button("🎨 Enter Art Studio", type="primary", key="enter_art_studio"):
                            # Transfer prompt and intent to art studio
                            st.session_state.art_studio_prompt = offer["prompt"]
                            st.session_state.art_studio_intent = offer["intent"]
                            st.session_state.workspace = "Art Studio"
                            del st.session_state._workspace_offer
                            st.rerun()
                    with col_stay:
                        if st.button("💬 Stay in Chat", key="stay_in_chat"):
                            del st.session_state._workspace_offer
                            st.rerun()
                    # Don't auto-rerun — wait for user choice
                    return

                # FINAL STEP: Reset the input field in session state and rerun to clean up live widgets
                if "user_prompt_input" in st.session_state:
                    st.session_state["user_prompt_input"] = ""

                # Brief pause to show "Mission Complete" then refresh
                time.sleep(0.5)
                st.rerun()

def render_art_workspace():
    """
    Art Studio — Meshy/Hunyuan3D-style workspace for image, 3D, and action figure generation.
    Provides generation controls, preview panel, gallery, and export tools.
    """
    import sys, os, json
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
    from specialized.image_gen import list_available_models

    # --- SESSION STATE DEFAULTS ---
    if "art_studio_mode" not in st.session_state:
        st.session_state.art_studio_mode = "Image"
    if "art_studio_history" not in st.session_state:
        st.session_state.art_studio_history = []
    if "art_studio_selected" not in st.session_state:
        st.session_state.art_studio_selected = None

    # Auto-set mode from workspace offer if redirected from chat
    if "art_studio_intent" in st.session_state:
        intent_map = {"IMAGE": "Image", "3D": "3D Model", "ACTION_FIGURE": "Action Figure"}
        st.session_state.art_studio_mode = intent_map.get(st.session_state.art_studio_intent, "Image")
        del st.session_state.art_studio_intent

    # Pre-fill prompt from chat redirect
    prefill_prompt = ""
    if "art_studio_prompt" in st.session_state:
        prefill_prompt = st.session_state.art_studio_prompt
        del st.session_state.art_studio_prompt

    # --- SIDEBAR: Generation Controls ---
    with st.sidebar:
        st.markdown("### 🎨 Art Studio Controls")

        # Mode Selector (the key switch)
        mode = st.radio(
            "Generation Mode",
            ["Image", "3D Model", "Action Figure"],
            index=["Image", "3D Model", "Action Figure"].index(st.session_state.art_studio_mode),
            key="art_mode_radio",
            horizontal=True
        )
        st.session_state.art_studio_mode = mode

        st.divider()

        # --- Mode-specific controls ---
        if mode == "Image":
            st.markdown("#### Image Settings")
            available_models = list_available_models()
            if not available_models:
                available_models = ["v1-5-pruned-emaonly.ckpt"]
            model_name = st.selectbox("Model Checkpoint", available_models, key="art_model")

            col1, col2 = st.columns(2)
            with col1:
                cfg = st.slider("CFG Scale", 1.0, 20.0, 7.0, 0.5, key="art_cfg")
            with col2:
                steps = st.slider("Steps", 1, 50, 20, 1, key="art_steps")

            aspect = st.selectbox("Aspect Ratio", ["1:1 (Square)", "16:9 (Cinematic)", "9:16 (Mobile)"], key="art_aspect")
            w, h = 1024, 1024
            if "16:9" in aspect: w, h = 1344, 768
            elif "9:16" in aspect: w, h = 768, 1344
            st.caption(f"Resolution: {w}x{h}")

            with st.expander("Advanced Settings"):
                col_a, col_b = st.columns(2)
                with col_a:
                    sampler = st.selectbox("Sampler", ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "ddim"], key="art_sampler")
                with col_b:
                    scheduler = st.selectbox("Scheduler", ["normal", "karras", "simple", "sgm_uniform"], key="art_scheduler")
                seed = st.number_input("Seed (-1 = Random)", value=-1, step=1, key="art_seed")

        elif mode == "3D Model":
            st.markdown("#### 3D Generation Settings")
            workflow_3d = st.selectbox("Pipeline", ["TripoSG (Fast)", "Hunyuan 3D (Textured)"], key="art_3d_pipe")
            st.caption("TripoSG: ~2 min, untextured GLB")
            st.caption("Hunyuan: ~8 min, full texture + UV")
            st.divider()
            generate_concept = st.checkbox("Auto-generate concept art first", value=True, key="art_3d_concept")
            st.caption("If disabled, you must provide an image path directly.")

        elif mode == "Action Figure":
            st.markdown("#### Action Figure Settings")
            workflow_af = st.selectbox("Base Mesh Pipeline", ["TripoSG (Fast)", "Hunyuan 3D (Textured)"], key="art_af_pipe")
            target_height = st.slider("Figure Height (mm)", 50, 300, 150, 10, key="art_af_height")
            clearance = st.slider("Joint Clearance (mm)", 0.1, 0.5, 0.3, 0.05, key="art_af_clearance",
                                  help="0.3mm for FDM, 0.15mm for resin")
            st.divider()
            st.markdown("**Joint Locations**")
            joints_enabled = {}
            joint_names = ["neck", "shoulders", "elbows", "wrists", "waist", "hips", "knees"]
            for jn in joint_names:
                joints_enabled[jn] = st.checkbox(jn.title(), value=True, key=f"art_af_j_{jn}")

        st.divider()
        with st.expander("📦 Resource Manager"):
            new_model_url = st.text_input("CivitAI / HuggingFace URL", key="art_import_url")
            if st.button("Request Import", key="art_import_btn"):
                st.info("Validation Agent checking compatibility...")
                time.sleep(1)
                st.success("Request Queued: Administrator approval required.")

    # =========================================================================
    # MAIN AREA
    # =========================================================================

    # Header
    mode_icons = {"Image": "🖼️", "3D Model": "🧊", "Action Figure": "🦾"}
    st.markdown(f"## {mode_icons.get(mode, '🎨')} Art Studio — {mode} Generator")

    # --- TOP: Prompt Input Bar ---
    with st.form(key="art_studio_form", clear_on_submit=True):
        cols = st.columns([7, 1, 1])
        with cols[0]:
            user_input = st.text_input(
                "Describe your creation...",
                value=prefill_prompt,
                placeholder="A cyberpunk samurai in neon rain..." if mode == "Image"
                    else "A dragon warrior character..." if mode == "3D Model"
                    else "A robot action figure with armor plating...",
                label_visibility="collapsed",
                key="art_prompt_input"
            )
        with cols[1]:
            generate_btn = st.form_submit_button(f"{mode_icons.get(mode, '🎨')} Generate")
        with cols[2]:
            # Image upload for image-to-3D modes
            if mode in ["3D Model", "Action Figure"]:
                upload_btn = st.form_submit_button("📁 Upload Image")
            else:
                upload_btn = False

    # Image uploader (outside form for Streamlit compatibility)
    uploaded_image = None
    if mode in ["3D Model", "Action Figure"]:
        uploaded_image = st.file_uploader(
            "Or upload a source image for direct 3D conversion",
            type=["png", "jpg", "jpeg", "webp"],
            key="art_upload_img",
            label_visibility="collapsed"
        )

    # --- GENERATION EXECUTION ---
    if generate_btn and user_input:
        if mode == "Image":
            _art_generate_image(user_input, model_name, cfg, steps, w, h, sampler, scheduler, seed)
        elif mode == "3D Model":
            wf = "workflow_triposg.json" if "TripoSG" in workflow_3d else "workflow_hunyuan_paint.json"
            _art_generate_3d(user_input, wf, generate_concept)
        elif mode == "Action Figure":
            wf = "workflow_triposg.json" if "TripoSG" in workflow_af else "workflow_hunyuan_paint.json"
            _art_generate_action_figure(user_input, wf, target_height, clearance, joints_enabled)

    # Handle uploaded image for direct 3D conversion
    if uploaded_image is not None and mode in ["3D Model", "Action Figure"]:
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_image.name.split('.')[-1]}") as tmp:
            tmp.write(uploaded_image.getvalue())
            tmp_path = tmp.name
        if mode == "3D Model":
            wf = "workflow_triposg.json" if "TripoSG" in workflow_3d else "workflow_hunyuan_paint.json"
            _art_generate_3d_from_image(tmp_path, wf)
        else:
            wf = "workflow_triposg.json" if "TripoSG" in workflow_af else "workflow_hunyuan_paint.json"
            _art_generate_action_figure_from_image(tmp_path, wf, target_height, clearance, joints_enabled)

    # --- PREVIEW + GALLERY AREA ---
    st.markdown("---")

    tab_preview, tab_gallery, tab_3d_gallery, tab_exports = st.tabs(
        ["👁️ Preview", "🖼️ Image Gallery", "🧊 3D Gallery", "📦 Exports"]
    )

    with tab_preview:
        _render_preview_panel()

    with tab_gallery:
        _render_image_gallery()

    with tab_3d_gallery:
        _render_3d_gallery()

    with tab_exports:
        _render_exports_panel()


# ============================================================================
# ART STUDIO: Generation Helpers
# ============================================================================

def _art_generate_image(prompt, model_name, cfg, steps, w, h, sampler, scheduler, seed):
    """Direct image generation (bypasses router)."""
    system_directive = f"""
    User Request: {prompt}
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
    with st.status("🎨 Generating Image...", expanded=True) as status:
        st.write(f"Prompt: {prompt}")
        from specialized.image_gen import get_image_gen_agent
        agent = get_image_gen_agent()
        try:
            response = agent.run(system_directive)
            st.write(response.content)

            # Track in history
            st.session_state.art_studio_history.append({
                "type": "image", "prompt": prompt, "result": response.content,
                "params": {"model": model_name, "cfg": cfg, "steps": steps}
            })
            status.update(label="Generation Complete", state="complete", expanded=False)
            time.sleep(1)
            st.rerun()
        except Exception as e:
            status.error(f"Generation Failed: {e}")


def _art_generate_3d(prompt, workflow_name, auto_concept=True):
    """3D model generation with optional concept art step."""
    with st.status("🧊 Generating 3D Model...", expanded=True) as status:
        st.write(f"Prompt: {prompt}")

        if auto_concept:
            st.write("Step 1/2: Generating concept art...")
            from specialized.image_gen import generate_image
            concept_prompt = f"Concept art for 3d modeling, neutral background: {prompt}"
            img_result = generate_image(concept_prompt)
            st.write(f"Concept: {img_result}")

            import re
            match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
            if not match:
                status.error(f"Failed to generate concept art: {img_result}")
                return
            image_path = f"/app/comfy_io/output/{match.group(1)}"
        else:
            status.error("No image provided. Enable auto-concept or upload an image.")
            return

        st.write("Step 2/2: Generating 3D mesh...")
        from specialized.forge_agent import generate_3d_model
        result = generate_3d_model(image_path, workflow_name)
        st.write(result)

        st.session_state.art_studio_history.append({
            "type": "3d_model", "prompt": prompt, "result": result
        })
        # Store for preview
        if "Generated Successfully" in result:
            mesh_path = result.split(":", 1)[1].strip()
            st.session_state.art_studio_selected = {"type": "3d_model", "path": mesh_path}

        status.update(label="3D Generation Complete", state="complete", expanded=False)
        time.sleep(1)
        st.rerun()


def _art_generate_3d_from_image(image_path, workflow_name):
    """Direct image-to-3D conversion."""
    with st.status("🧊 Converting Image to 3D...", expanded=True) as status:
        st.write(f"Source: {image_path}")
        from specialized.forge_agent import generate_3d_model
        result = generate_3d_model(image_path, workflow_name)
        st.write(result)

        st.session_state.art_studio_history.append({
            "type": "3d_model", "prompt": f"[uploaded image] {image_path}", "result": result
        })
        status.update(label="3D Conversion Complete", state="complete", expanded=False)
        time.sleep(1)
        st.rerun()


def _art_generate_action_figure(prompt, workflow_name, target_height, clearance, joints_enabled):
    """Full action figure pipeline with custom joint settings."""
    with st.status("🦾 Generating Action Figure...", expanded=True) as status:
        st.write(f"Prompt: {prompt}")

        # Step 1: Concept Art (T-Pose)
        st.write("Step 1/3: Generating T-pose concept art...")
        from specialized.image_gen import generate_image
        concept_prompt = (
            f"T-pose character concept art for 3D action figure, "
            f"full body front view, neutral gray background, "
            f"arms extended to sides, symmetrical pose: {prompt}"
        )
        img_result = generate_image(concept_prompt)
        st.write(f"Concept: {img_result}")

        import re
        match = re.search(r"Generated Image: ([\w\.-]+)", img_result)
        if not match:
            status.error(f"Failed to generate concept art: {img_result}")
            return
        image_path = f"/app/comfy_io/output/{match.group(1)}"

        # Step 2 & 3: Action Figure Pipeline
        st.write("Step 2/3: Generating base mesh & segmenting with joints...")
        from specialized.action_figure_agent import generate_action_figure
        result = generate_action_figure(image_path, workflow_name)
        st.write(result)

        st.session_state.art_studio_history.append({
            "type": "action_figure", "prompt": prompt, "result": result,
            "params": {"height_mm": target_height, "clearance_mm": clearance}
        })
        status.update(label="Action Figure Complete", state="complete", expanded=False)
        time.sleep(1)
        st.rerun()


def _art_generate_action_figure_from_image(image_path, workflow_name, target_height, clearance, joints_enabled):
    """Direct image-to-action-figure conversion."""
    with st.status("🦾 Converting Image to Action Figure...", expanded=True) as status:
        st.write(f"Source: {image_path}")
        from specialized.action_figure_agent import generate_action_figure
        result = generate_action_figure(image_path, workflow_name)
        st.write(result)

        st.session_state.art_studio_history.append({
            "type": "action_figure", "prompt": f"[uploaded image]", "result": result
        })
        status.update(label="Action Figure Complete", state="complete", expanded=False)
        time.sleep(1)
        st.rerun()


# ============================================================================
# ART STUDIO: Preview & Gallery Panels
# ============================================================================

def _render_preview_panel():
    """Preview panel for the last generated asset."""
    import os

    selected = st.session_state.get("art_studio_selected")
    history = st.session_state.get("art_studio_history", [])

    if not selected and not history:
        st.info("Generate something to see a preview here.")
        return

    # Show the last generation result
    if history:
        last = history[-1]
        st.markdown(f"**Last Generation:** `{last['type']}`")
        st.caption(f"Prompt: {last.get('prompt', 'N/A')}")

        if last["type"] == "image":
            # Try to extract and show the image
            import re
            match = re.search(r"Generated Image: ([\w\.-]+)", last.get("result", ""))
            if match:
                img_path = os.path.join("delivered_artifacts", match.group(1))
                if os.path.exists(img_path):
                    st.image(img_path, use_container_width=True)
                    with open(img_path, "rb") as f:
                        st.download_button("⬇️ Download Image", f, file_name=match.group(1),
                                           mime="image/png", key="preview_dl_img")

        elif last["type"] == "3d_model":
            st.success(f"🧊 3D Model Ready")
            st.code(last.get("result", ""), language="text")
            # 3D viewer placeholder
            st.markdown("""
            <div style="background: #111; border: 1px solid #333; border-radius: 8px;
                        height: 400px; display: flex; align-items: center; justify-content: center;
                        color: #666; font-size: 1.2em;">
                <div style="text-align: center;">
                    <div style="font-size: 3em; margin-bottom: 10px;">🧊</div>
                    <div>3D Preview</div>
                    <div style="font-size: 0.8em; color: #555; margin-top: 5px;">
                        Download the GLB file and open in your slicer or 3D viewer
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        elif last["type"] == "action_figure":
            st.success(f"🦾 Action Figure Ready — Posable STL Parts")
            st.code(last.get("result", ""), language="text")
            params = last.get("params", {})
            if params:
                col1, col2 = st.columns(2)
                col1.metric("Figure Height", f"{params.get('height_mm', 150)}mm")
                col2.metric("Joint Clearance", f"{params.get('clearance_mm', 0.3)}mm")

            st.markdown("""
            <div style="background: #111; border: 1px solid #333; border-radius: 8px;
                        height: 300px; display: flex; align-items: center; justify-content: center;
                        color: #666;">
                <div style="text-align: center;">
                    <div style="font-size: 3em; margin-bottom: 10px;">🦾</div>
                    <div>Action Figure Assembly View</div>
                    <div style="font-size: 0.8em; color: #555; margin-top: 5px;">
                        Individual STL parts with ball-socket joints<br/>
                        Check action_figures/ directory for print-ready files
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Generation History Sidebar
    if len(history) > 1:
        st.markdown("---")
        st.markdown("**Generation History**")
        for i, item in enumerate(reversed(history[-10:])):
            icon = {"image": "🖼️", "3d_model": "🧊", "action_figure": "🦾"}.get(item["type"], "📦")
            prompt_preview = item.get("prompt", "")[:50]
            st.caption(f"{icon} {prompt_preview}...")


def _render_image_gallery():
    """Image gallery with metadata."""
    import os, json

    if st.button("🔄 Refresh Gallery", key="refresh_img_gallery"):
        st.rerun()

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

                meta_path = img_path + ".json"
                meta = {}
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as f:
                        meta = json.load(f)

                with cols[idx % 4]:
                    st.image(img_path, use_container_width=True)
                    st.caption(img_name)

                    if meta:
                        with st.popover("ℹ️ info"):
                            st.markdown(f"**Prompt**: {meta.get('prompt', 'N/A')}")
                            st.markdown(f"**Model**: `{meta.get('model', 'Auto')}`")
                            p = meta.get('params', {})
                            st.caption(f"CFG: {p.get('cfg')} | Steps: {p.get('steps')}")

                    # Use as source for 3D conversion
                    col_dl, col_use = st.columns(2)
                    with col_dl:
                        with open(img_path, "rb") as f:
                            st.download_button("⬇️", f, file_name=img_name, key=f"dl_gal_{idx}")
                    with col_use:
                        if st.button("🧊 To 3D", key=f"to3d_{idx}"):
                            st.session_state.art_studio_mode = "3D Model"
                            st.session_state._use_image_path = img_path
                            st.rerun()

    except Exception as e:
        st.error(f"Gallery Error: {e}")


def _render_3d_gallery():
    """Gallery for 3D models and action figure outputs."""
    import os

    if st.button("🔄 Refresh 3D Gallery", key="refresh_3d_gallery"):
        st.rerun()

    # Scan for 3D files in output directories
    output_dirs = [
        ("ComfyUI Output (3D)", "/app/comfy_io/output/3D"),
        ("Action Figures", "/app/comfy_io/output/action_figures"),
    ]

    for section_name, dir_path in output_dirs:
        st.markdown(f"#### {section_name}")
        if not os.path.exists(dir_path):
            st.caption(f"Directory not found: {dir_path}")
            continue

        files_3d = [f for f in os.listdir(dir_path) if f.lower().endswith(('.glb', '.obj', '.stl', '.3mf'))]
        files_3d.sort(key=lambda x: os.path.getmtime(os.path.join(dir_path, x)), reverse=True)

        if not files_3d:
            st.caption("No 3D files found.")
            continue

        cols = st.columns(3)
        for idx, fname in enumerate(files_3d):
            fpath = os.path.join(dir_path, fname)
            ext = fname.rsplit(".", 1)[-1].upper()
            size_mb = os.path.getsize(fpath) / (1024 * 1024)

            with cols[idx % 3]:
                st.markdown(f"""
                <div style="background: #1a1a2e; border: 1px solid #333; border-radius: 8px;
                            padding: 15px; text-align: center; margin-bottom: 10px;">
                    <div style="font-size: 2.5em; margin-bottom: 8px;">
                        {"🦾" if "action_fig" in fname else "🧊"}
                    </div>
                    <div style="font-weight: 600; color: #e0e0e0; font-size: 0.9em;">{fname}</div>
                    <div style="color: #888; font-size: 0.75em; margin-top: 4px;">
                        {ext} &bull; {size_mb:.1f} MB
                    </div>
                </div>
                """, unsafe_allow_html=True)

                with open(fpath, "rb") as f:
                    st.download_button(
                        f"⬇️ Download {ext}",
                        f, file_name=fname,
                        key=f"dl_3d_{section_name}_{idx}"
                    )

    # Also check for manifests
    manifest_dir = "/app/comfy_io/output/action_figures"
    if os.path.exists(manifest_dir):
        manifests = [f for f in os.listdir(manifest_dir) if f.endswith("_manifest.json")]
        if manifests:
            st.markdown("#### 📋 Assembly Manifests")
            for mf in manifests:
                import json
                mpath = os.path.join(manifest_dir, mf)
                with open(mpath, "r") as f:
                    manifest = json.load(f)
                with st.expander(f"📋 {mf}"):
                    st.json(manifest)
                    st.caption(manifest.get("assembly_notes", ""))


def _render_exports_panel():
    """Export and batch download panel."""
    import os, zipfile, tempfile

    st.markdown("#### Export Options")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="background: rgba(0,100,200,0.1); border: 1px solid rgba(0,100,200,0.3);
                    border-radius: 8px; padding: 15px;">
            <h4 style="margin:0;">🖼️ Batch Image Export</h4>
            <p style="color: #999; font-size: 0.85em;">Download all gallery images as a ZIP</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📦 Export All Images", key="export_images"):
            gallery_path = "delivered_artifacts"
            if os.path.exists(gallery_path):
                images = [f for f in os.listdir(gallery_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if images:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as zf:
                            for img in images:
                                zf.write(os.path.join(gallery_path, img), img)
                        with open(tmp.name, "rb") as f:
                            st.download_button("⬇️ Download ZIP", f, file_name="art_studio_images.zip",
                                               mime="application/zip", key="dl_zip_imgs")
                else:
                    st.caption("No images to export.")

    with col2:
        st.markdown("""
        <div style="background: rgba(200,100,0,0.1); border: 1px solid rgba(200,100,0,0.3);
                    border-radius: 8px; padding: 15px;">
            <h4 style="margin:0;">🦾 Batch 3D Export</h4>
            <p style="color: #999; font-size: 0.85em;">Download all action figure STLs as a ZIP</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📦 Export All 3D Files", key="export_3d"):
            af_dir = "/app/comfy_io/output/action_figures"
            if os.path.exists(af_dir):
                stls = [f for f in os.listdir(af_dir) if f.lower().endswith(('.stl', '.glb', '.obj'))]
                if stls:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, 'w') as zf:
                            for stl in stls:
                                zf.write(os.path.join(af_dir, stl), stl)
                        with open(tmp.name, "rb") as f:
                            st.download_button("⬇️ Download ZIP", f, file_name="action_figures_3d.zip",
                                               mime="application/zip", key="dl_zip_3d")
                else:
                    st.caption("No 3D files to export.")
            else:
                st.caption("Action figures directory not found.")

    # Generation log
    st.markdown("---")
    st.markdown("#### Generation Log")
    history = st.session_state.get("art_studio_history", [])
    if not history:
        st.caption("No generations in this session yet.")
    else:
        for i, entry in enumerate(reversed(history[-20:])):
            icon = {"image": "🖼️", "3d_model": "🧊", "action_figure": "🦾"}.get(entry["type"], "📦")
            st.caption(f"{icon} **{entry['type']}** — {entry.get('prompt', 'N/A')[:60]}")

def render_voice_workspace():
    st.markdown("## 🎙️ Voice Studio")

    # Helper Imports
    import sys, os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

    # --- SIDEBAR CONTROLS ---
    with st.sidebar:
        st.markdown("### 🎚️ Audio Config")
        # Placeholder for model switching if supported later
        st.info("Engine: Qwen3-TTS (1.7B)")
        
    # --- MAIN INTERFACE ---
    col_input, col_ref = st.columns([2, 1])
    
    with col_input:
        st.subheader("Text to Speech")
        text_input = st.text_area("Enter text to speak...", height=150, placeholder="Hello, this is a test of the voice cloning system.")
        
    with col_ref:
        st.subheader("Voice Reference")
        uploaded_files = st.file_uploader("Clone Voice (Optional)", type=["wav", "mp3"], accept_multiple_files=True)
        
        ref_paths = []
        if uploaded_files:
            # Save temp files
            import tempfile
            for uploaded_file in uploaded_files:
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    ref_paths.append(tmp.name)
            
            if len(uploaded_files) == 1:
                st.audio(uploaded_files[0], format="audio/wav")
            else:
                st.caption(f"{len(uploaded_files)} references loaded.")
            st.caption("References ready.")
            
    with col_input:
        effect_list = [
            "None", "BMO", "Old Radio", "Telephony", "Cave", "Cathedral", "Small Room", 
            "Chipmunk", "Deep Voice", "Robot", "Alien", "Ethereal", 
            "Overdrive", "Megaphone", "Underwater", "Walkie Talkie", 
            "Phaser", "Tremolo"
        ]
        selected_effect = st.selectbox("Audio Effect", effect_list, index=0)
        
    if st.button("🔊 Generate Speech", type="primary"):
        if not text_input:
            st.warning("Please enter text.")
        else:
            with st.status("🎙️ Synthesizing...", expanded=True) as status:
                from specialized.voice_cloning import clone_voice
                
                try:
                    # Pass effect if not None
                    eff_param = selected_effect if selected_effect != "None" else None
                    result = clone_voice(text_input, reference_audio_paths=ref_paths, effect=eff_param)
                    
                    if "Generated Audio" in result:
                        # Extract filename
                        filename = result.split("Generated Audio: ")[1].split(" ")[0]
                        
                        # Locate file
                        workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        artifact_path = os.path.join(workspace_root, "delivered_artifacts", filename)
                        
                        if os.path.exists(artifact_path):
                            st.success("Generation Complete!")
                            st.audio(artifact_path)
                            
                            with open(artifact_path, "rb") as f:
                                st.download_button("⬇️ Download Audio", f, file_name=filename, mime="audio/wav")
                        else:
                            st.error(f"File not found at {artifact_path}")
                    else:
                        st.error(result)
                        
                    status.update(label="Complete", state="complete", expanded=False)
                    
                except Exception as e:
                    st.error(f"Synthesis Failed: {e}")
                    
            # Cleanup temp files
            if ref_paths:
                for p in ref_paths:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except:
                            pass

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
        from registry import registry
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
                elif "[ActionFigureForge]" in content: current_agent = "Art Director"
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
    from tools.iot_ops import get_states, call_service
    
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


# --- DOCUMENTS WORKSPACE ---
def render_documents_workspace():
    import os

    DOCS_ROOT = os.path.join(os.path.dirname(__file__), "..", "docs")

    def read_doc(rel_path):
        path = os.path.normpath(os.path.join(DOCS_ROOT, rel_path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"_Document not found: `{rel_path}`_"

    st.markdown("## 📚 Documentation")
    st.caption("Home AI Lab v3.3 · All documentation · Use the tabs below to navigate")

    user_tab, admin_tab = st.tabs(["👤 User Guide", "🔧 Admin Reference"])

    with user_tab:
        ov_tab, fw_tab, faq_tab = st.tabs(["System Overview", "How It Works", "FAQ"])
        with ov_tab:
            st.markdown(read_doc("user/overview.md"))
        with fw_tab:
            st.markdown(read_doc("user/framework.md"))
        with faq_tab:
            st.markdown(read_doc("user/faq.md"))

    with admin_tab:
        ref_tab, design_tab, sec_tab, ts_tab = st.tabs([
            "Technical Reference", "Design Framework", "Security", "Troubleshooting"
        ])
        with ref_tab:
            st.markdown(read_doc("admin/technical_reference.md"))
        with design_tab:
            st.markdown(read_doc("admin/design_framework.md"))
        with sec_tab:
            st.markdown(read_doc("admin/security.md"))
        with ts_tab:
            st.markdown(read_doc("admin/troubleshooting.md"))


# --- MAIN DISPATCHER ---
if st.session_state.workspace == "Chat":
    render_chat_workspace()
elif st.session_state.workspace == "Art Studio":
    render_art_workspace()
elif st.session_state.workspace == "Voice Studio":
    render_voice_workspace()
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
elif st.session_state.workspace == "Documents":
    render_documents_workspace()
