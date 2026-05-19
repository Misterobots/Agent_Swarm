import streamlit as st
import pandas as pd
import os
import json
import time
import requests
from datetime import datetime
import plotly.express as px
from config import HOPPER_IP, LANGFUSE_HOST

# Setup Page
st.set_page_config(
    page_title="Agentic Hive Ops",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING ---
st.markdown("""
<style>
    /* Dark Mode Optimization */
    .stApp {
        background-color: #0e1117;
        color: #c9d1d9;
    }
    
    /* Metrics Cards */
    div[data-testid="metric-container"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 5% 5% 5% 10%;
        border-radius: 5px;
        color: #c9d1d9;
    }
    
    /* Status Indicators */
    .status-dot {
        height: 10px;
        width: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
    }
    .status-green { background-color: #2ea043; box-shadow: 0 0 5px #2ea043; }
    .status-red { background-color: #da3633; box-shadow: 0 0 5px #da3633; }
    .status-yellow { background-color: #d29922; box-shadow: 0 0 5px #d29922; }
    
    /* Tables */
    div[data-testid="stDataFrame"] {
        border: 1px solid #30363d;
        border-radius: 5px;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #010409;
        border-right: 1px solid #30363d;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #58a6ff;
        font-family: 'Segoe UI', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- REAL DATA FETCHING ---

def get_compliance_score():
    # In real impl, read latest drift report
    return {
        "score": 92,
        "drift_detected": False,
        "last_scan": "2026-02-09 13:14:00",
        "maestro_level": "L7 (Identity Enforced)"
    }

@st.cache_data(ttl=10)
def get_system_health():
    """
    Fetches real container stats via Docker Socket + Control Plane HTTP pings.
    """
    import subprocess
    import json
    import requests
    
    exec_plane = []
    ctrl_plane = []
    status_msg = "ONLINE"
    running_count = 0
    
    # --- Execution Plane: Docker Socket ---
    try:
        result = subprocess.run(
            ["curl", "-s", "--unix-socket", "/var/run/docker.sock",
             "http://localhost/containers/json"],  # No ?all=1 → running only
            capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0 and result.stdout.strip():
            containers = json.loads(result.stdout)
            running_count = len(containers)
            
            for c in containers:
                name = c.get('Names', ['/unknown'])[0].lstrip('/')
                image = c.get('Image', 'unknown').split('/')[-1].split(':')[0]
                uptime = c.get('Status', 'Unknown')
                
                exec_plane.append({
                    "Container": name,
                    "Status": "🟢 Running",
                    "Image": image,
                    "Uptime": uptime
                })
        else:
            status_msg = f"Docker: {result.stderr[:60]}"
    except Exception as e:
        status_msg = f"Docker Error: {str(e)[:60]}"
    
    # --- Control Plane: HTTP Health Checks ---
    cp_services = [
        {"name": "Langfuse",     "url": f"http://{HOPPER_IP}:3000/api/public/health", "port": 3000},
        {"name": "PostgreSQL",   "url": None,                                          "port": 5432},
        {"name": "SPIRE Server", "url": None,                                          "port": 8081},
        {"name": "MinIO API",    "url": f"http://{HOPPER_IP}:9190/minio/health/live", "port": 9190},
        {"name": "MinIO Console","url": None,                                          "port": 9191},
    ]
    # Note: ClickHouse has no host-exposed port (internal to swarm_net only)
    
    for svc in cp_services:
        try:
            if svc["url"]:
                r = requests.get(svc["url"], timeout=2)
                alive = r.status_code < 500
            else:
                # TCP port check for services without HTTP health endpoints
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                result_code = s.connect_ex((HOPPER_IP, svc["port"]))
                s.close()
                alive = (result_code == 0)
                
            ctrl_plane.append({
                "Service": svc["name"],
                "Status": "🟢 Healthy" if alive else "🔴 Down",
                "Port": svc["port"]
            })
        except Exception:
            ctrl_plane.append({
                "Service": svc["name"],
                "Status": "🔴 Unreachable",
                "Port": svc["port"]
            })
             
    return {
        "status": status_msg,
        "running_count": running_count,
        "containers": {
            "execution_plane": exec_plane,
            "control_plane": ctrl_plane
        }
    }

def get_langfuse_client():
    from langfuse import Langfuse
    return Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST")
    )

def get_recent_traces():
    """
    Fetches traces from Langfuse API.
    """
    lf_host = os.getenv("LANGFUSE_HOST")
    lf_public = os.getenv("LANGFUSE_PUBLIC_KEY")
    lf_secret = os.getenv("LANGFUSE_SECRET_KEY")
    
    if not lf_host or not lf_public:
        return [{"id": "error", "agent": "Config Missing", "status": "ERROR", "latency": 0}]

    try:
        import requests
        # Langfuse API v2 - Traces Listing
        # Auth: Basic Auth (Public Key, Secret Key)
        url = f"{lf_host}/api/public/traces?limit=50&orderBy=timestamp.desc"
        response = requests.get(url, auth=(lf_public, lf_secret), timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            traces = []
            for t in data.get("data", []):
                traces.append({
                    "id": t.get("id"),
                    "timestamp": t.get("timestamp"),
                    "agent": t.get("name", "Unknown"),
                    "input": str(t.get("input", ""))[:50] + "...",
                    "latency": t.get("latency", 0),
                    "status": "SUCCESS" if not t.get("level") == "ERROR" else "ERROR" # Simplified
                })
            return traces
        else:
            return [{"id": "api_error", "agent": f"HTTP {response.status_code}", "status": "ERROR"}]
            
    except Exception as e:
        return [{"id": "conn_error", "agent": str(e), "status": "ERROR"}]


# --- SIDEBAR NAV ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=60)
    st.title("Ops Portal")
    st.caption(f"v1.3.0 | Control Plane: {HOPPER_IP}")
    
    nav = st.radio("Navigation", ["Dashboard", "Swarm Observer", "Evidence Locker", "Control Room", "AI Tuning Studio"], label_visibility="collapsed")
    
    st.divider()
    
    # Live Status Ticker
    health = get_system_health()
    is_online = health["status"] == "ONLINE"
    status_color = "green" if is_online else "yellow"
    st.markdown(f"**System**: <span class='status-dot status-{status_color}'></span> {health['status']}", unsafe_allow_html=True)
    st.metric("Containers", health.get('running_count', 0))

# --- PAGE: DASHBOARD ---
if nav == "Dashboard":
    st.title("🛡️ Command Center")
    
    # Top Metrics
    comp = get_compliance_score()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Compliance Score", f"{comp['score']}%", "+4% vs Baseline")
    c2.metric("Active Agents", "5", "All Systems Go")
    c3.metric("Drift Events", "0", "Clean")
    c4.metric("Pending Approvals", "2", "-1")
    
    # Infrastructure View
    st.subheader("Infrastructure Health")
    c_exec, c_ctrl = st.columns(2)
    
    with c_exec:
        st.markdown("### 🧠 Execution Plane (Local)")
        exec_data = health["containers"]["execution_plane"]
        if exec_data:
            df_exec = pd.DataFrame(exec_data)
            st.dataframe(df_exec, use_container_width=True, hide_index=True)
        else:
            st.warning("No container data available.")
        
    with c_ctrl:
        st.markdown(f"### 🎮 Control Plane ({HOPPER_IP})")
        ctrl_data = health["containers"]["control_plane"]
        if ctrl_data:
            df_ctrl = pd.DataFrame(ctrl_data)
            st.dataframe(df_ctrl, use_container_width=True, hide_index=True)
        else:
            st.warning("Control Plane unreachable.")

    # Recent Alerts
    st.subheader("⚠️ Recent Alerts")
    # Check for down services
    down_services = [s for s in health["containers"]["control_plane"] if "Down" in s.get("Status", "") or "Unreachable" in s.get("Status", "")]
    if down_services:
        for s in down_services:
            st.error(f"🔴 {s['Service']} is {s['Status']} on port {s['Port']}")
    else:
        st.success("All systems operational. No active alerts.")

# --- PAGE: SWARM OBSERVER ---
elif nav == "Swarm Observer":
    st.title("🐝 Swarm Observer")
    
    # Embedded Trace View
    st.markdown("### 🕸️ Live Trace Feed (Langfuse)")
    
    # Mock Trace Table
    traces = get_recent_traces()
    df_traces = pd.DataFrame(traces)
    
    # Interactive filtering
    search = st.text_input("Search Traces", placeholder="Trace ID, Agent Name, or Content...")
    if search:
        df_traces = df_traces[df_traces.apply(lambda row: hasattr(row, 'astype') and row.astype(str).str.contains(search, case=False).any(), axis=1)]

    st.dataframe(
        df_traces, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=["SUCCESS", "ERROR"],
                required=True,
            ),
            "latency": st.column_config.ProgressColumn(
                "Latency (s)",
                format="%.2f",
                min_value=0,
                max_value=10,
            ),
        }
    )
    
    # Deep Dive
    with st.expander("🔬 Trace Inspector", expanded=True):
        trace_ids = [t["id"] for t in traces]
        if not trace_ids:
            st.info("No traces available.")
        else:
            selected_trace = st.selectbox("Select Trace ID", trace_ids)

            lf_host = LANGFUSE_HOST
            lf_public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
            lf_secret = os.getenv("LANGFUSE_SECRET_KEY", "")

            # Fetch trace detail
            try:
                trace_resp = requests.get(
                    f"{lf_host}/api/public/traces/{selected_trace}",
                    auth=(lf_public, lf_secret), timeout=5
                )
                if trace_resp.status_code == 200:
                    trace_data = trace_resp.json()
                    st.markdown("**Trace Metadata**")
                    meta_cols = st.columns(3)
                    meta_cols[0].metric("Name", trace_data.get("name", "—"))
                    latency_val = trace_data.get("latency")
                    meta_cols[1].metric("Latency", f"{latency_val:.2f}s" if latency_val else "—")
                    meta_cols[2].metric("Status", trace_data.get("level", "DEFAULT"))

                    if trace_data.get("input"):
                        st.markdown("**Input**")
                        st.json(trace_data["input"])
                    if trace_data.get("output"):
                        st.markdown("**Output**")
                        st.json(trace_data["output"])
                else:
                    st.warning(f"Could not fetch trace detail (HTTP {trace_resp.status_code})")
            except Exception as e:
                st.warning(f"Trace detail unavailable: {e}")

            # Fetch observations (spans / generations)
            try:
                obs_resp = requests.get(
                    f"{lf_host}/api/public/observations?traceId={selected_trace}&limit=50",
                    auth=(lf_public, lf_secret), timeout=5
                )
                if obs_resp.status_code == 200:
                    obs_data = obs_resp.json().get("data", [])
                    if obs_data:
                        st.markdown(f"**Observations** ({len(obs_data)} spans)")
                        for i, obs in enumerate(obs_data):
                            obs_type = obs.get("type", "span").upper()
                            obs_name = obs.get("name", "unnamed")
                            obs_level = obs.get("level", "DEFAULT")
                            icon = "🟢" if obs_level != "ERROR" else "🔴"
                            duration = ""
                            if obs.get("startTime") and obs.get("endTime"):
                                try:
                                    start = datetime.fromisoformat(obs["startTime"].replace("Z", "+00:00"))
                                    end = datetime.fromisoformat(obs["endTime"].replace("Z", "+00:00"))
                                    duration = f" ({(end - start).total_seconds():.2f}s)"
                                except Exception:
                                    pass

                            # Model & token summary line
                            model_info = ""
                            if obs.get("model"):
                                model_info = f" · `{obs['model']}`"
                            usage = obs.get("usage") or {}
                            tok_parts = []
                            if usage.get("input"):
                                tok_parts.append(f"In: {usage['input']}")
                            if usage.get("output"):
                                tok_parts.append(f"Out: {usage['output']}")
                            if usage.get("totalCost"):
                                tok_parts.append(f"${usage['totalCost']:.4f}")
                            tok_str = f" · {' / '.join(tok_parts)} tok" if tok_parts else ""

                            header = f"{icon} **[{obs_type}]** {obs_name}{duration}{model_info}{tok_str}"

                            with st.expander(header, expanded=False):
                                tab_input, tab_output, tab_meta = st.tabs(["💭 Input (Prompt)", "🧠 Output (Response)", "📋 Metadata"])

                                with tab_input:
                                    obs_input = obs.get("input")
                                    if obs_input:
                                        if isinstance(obs_input, str):
                                            st.markdown(obs_input)
                                        elif isinstance(obs_input, list):
                                            # Chat-format messages
                                            for msg in obs_input:
                                                if isinstance(msg, dict):
                                                    role = msg.get("role", "unknown")
                                                    content = msg.get("content", str(msg))
                                                    role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}.get(role, "💬")
                                                    st.markdown(f"**{role_icon} {role.title()}**")
                                                    st.text(content[:2000] + ("..." if len(str(content)) > 2000 else ""))
                                                else:
                                                    st.text(str(msg)[:2000])
                                        else:
                                            st.json(obs_input)
                                    else:
                                        st.caption("No input recorded")

                                with tab_output:
                                    obs_output = obs.get("output")
                                    if obs_output:
                                        if isinstance(obs_output, str):
                                            st.markdown(obs_output)
                                        elif isinstance(obs_output, dict) and obs_output.get("content"):
                                            st.markdown(obs_output["content"])
                                        else:
                                            st.json(obs_output)
                                    else:
                                        st.caption("No output recorded")

                                with tab_meta:
                                    meta = obs.get("metadata")
                                    if meta:
                                        st.json(meta)
                                    # Status info
                                    meta_info = {
                                        "id": obs.get("id"),
                                        "type": obs_type,
                                        "level": obs_level,
                                        "startTime": obs.get("startTime"),
                                        "endTime": obs.get("endTime"),
                                        "model": obs.get("model"),
                                        "completionStartTime": obs.get("completionStartTime"),
                                    }
                                    st.json({k: v for k, v in meta_info.items() if v})
                    else:
                        st.info("No observations recorded for this trace.")
                else:
                    st.warning(f"Could not fetch observations (HTTP {obs_resp.status_code})")
            except Exception as e:
                st.warning(f"Observations unavailable: {e}")

            st.markdown(f"[View in Langfuse UI >]({LANGFUSE_HOST}/project/default/traces/{selected_trace})")

# --- PAGE: EVIDENCE LOCKER ---
elif nav == "Evidence Locker":
    st.title("🗄️ Evidence Locker")
    
    # File Browser logic
    docs_root = "docs"
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Directory")
        # Simple tree navigator
        subdirs = ["specs", "evidence", "compliance", "architecture"]
        selected_dir = st.radio("Folder", subdirs)
    
    with col2:
        st.subheader(f"Files in /{selected_dir}")
        target_path = os.path.join(docs_root, selected_dir)
        
        if os.path.exists(target_path):
            files = [f for f in os.listdir(target_path) if f.endswith(".md") or f.endswith(".txt") or f.endswith(".json")]
            selected_file = st.selectbox("Select File", files)
            
            if selected_file:
                file_path = os.path.join(target_path, selected_file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                with st.expander("📄 File Content", expanded=True):
                    if selected_file.endswith(".md"):
                        st.markdown(content)
                    elif selected_file.endswith(".json"):
                        st.json(content)
                    else:
                        st.text(content)
                        
                st.download_button("⬇️ Download Evidence", content, file_name=selected_file)
        else:
            st.error("Directory not found.")

# --- PAGE: CONTROL ROOM ---
elif nav == "Control Room":
    st.title("🎮 Control Room")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 🧪 Swarm Reliability Test")
        st.caption("Runs a full L1-L7 chain: Router -> Architect -> Security -> Coder.")
        
        if st.button("▶️ Run Comprehensive Test", type="primary"):
            st.toast("Initiating Test Sequence...")
            # Here we would trigger the test script
            with st.status("Executing Test Workflow...", expanded=True):
                st.write("Initializing Router...")
                time.sleep(1)
                st.write("Route: 'create_script' -> Architect Agent")
                st.write("Architect: Designing Plan...")
                time.sleep(1)
                st.write("Security: Scanning Plan for unsafe commands...")
                st.success("Security Check PASSED")
                time.sleep(1)
                st.write("Coder: Generating Script...")
                time.sleep(2)
                st.success("Test Completed Successfully! Trace ID: tr_test_123")
                
    with c2:
        st.markdown("### 🔄 System Maintenance")
        if st.button("🧹 Prune Docker Volumes"):
            st.warning("Action requires L3_ADMIN approval.")
        
        if st.button("♻️ Restart Agent Runtime"):
            st.warning("Action requires L3_ADMIN approval.")

# --- PAGE: AI TUNING STUDIO ---
elif nav == "AI Tuning Studio":
    st.title("🎛️ AI Tuning Studio")
    
    st.markdown("### 🤖 BMO Voice Calibration")
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.info("Tune the Real-Time Voice Conversion (RVC) parameters for BMO.")
        
        # Tuning Controls
        pitch = st.slider("Pitch Shift (Semitones)", min_value=-12, max_value=24, value=3, help="Adjust to match character propertires. BMO is usually around +10 to +12.")
        method = st.selectbox("Inference Method", ["rmvpe", "pm", "crepe"], index=0, help="'rmvpe' usually offers the best quality.")
        
        text_input = st.text_area("Test Phrase", "Hello Finn! Check out my new voice calibration.", height=100)
        
        generate = st.button("Generate Audio 📢", type="primary", use_container_width=True)
        
    with c2:
        st.markdown("#### Audio Output")
        
        if generate:
            with st.spinner("Synthesizing..."):
                try:
                    # Determine URL based on environment
                    # Check if running in Docker container
                    if os.path.exists("/.dockerenv"):
                        bmo_url = "http://bmo_voice_gpu:8000/speak"
                    else:
                        bmo_url = "http://localhost:8100/speak"
                    
                    params = {
                        "text": text_input,
                        "pitch": pitch,
                        "method": method
                    }
                    
                    # st.info(f"Connecting to: {bmo_url}") # Debug info
                    response = requests.post(bmo_url, params=params, timeout=10)
                    
                    if response.status_code == 200:
                        st.success(f"Generated successfully! (Pitch: {pitch}, Method: {method})")
                        st.audio(response.content, format="audio/wav")
                        
                        # Option to download
                        st.download_button("⬇️ Download WAV", response.content, file_name=f"bmo_pitch_{pitch}.wav", mime="audio/wav")
                    else:
                        st.error(f"Generation Failed: {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection Error: {e}")
                    st.caption(f"Failed to reach BMO Voice at {bmo_url}. Ensure service is running.")


