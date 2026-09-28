
import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px

DRIFT_FILE = ".drift/source-of-truth.json"

def load_drift_data():
    if not os.path.exists(DRIFT_FILE):
        return None
    try:
        with open(DRIFT_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load Drift Data: {e}")
        return None

def render_governance_workspace():
    st.header("🛡️ Governance & Compliance (MAESTRO L6)")
    
    data = load_drift_data()
    
    if not data:
        st.warning(f"⚠️ Drift Index not found at `{DRIFT_FILE}`. Please run `drift setup` in the terminal.")
        return

    # Extract Metrics
    baseline = data.get("baseline", {})
    total_patterns = baseline.get("patternCount", 0)
    approved = baseline.get("approvedCount", 0)
    compliance_score = (approved / total_patterns * 100) if total_patterns > 0 else 0
    
    # Top Level Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Compliance Score", f"{compliance_score:.1f}%", delta=f"{approved} Approved")
    with col2:
        st.metric("Total Patterns", total_patterns)
    with col3:
        st.metric("Files Indexed", baseline.get("fileCount", 0))
    with col4:
        st.metric("Drift Version", data.get("version", "N/A"))

    st.markdown("---")

    # Categories Chart
    categories = baseline.get("categories", {})
    if categories:
        df = pd.DataFrame(list(categories.items()), columns=["Category", "Count"])
        fig = px.bar(df, x="Category", y="Count", title="Pattern Distribution by Category", color="Count", color_continuous_scale="Viridis")
        st.plotly_chart(fig, use_container_width=True)

    # Tabs for Details
    tab1, tab2, tab3 = st.tabs(["🔍 Inspector", "📜 Audit Log", "🧩 Features"])
    
    with tab1:
        st.subheader("Source of Truth")
        st.json(data)
        
    with tab2:
        st.subheader("Recent Activity")
        history = data.get("history", [])
        if history:
            st.table(history)
        else:
            st.info("No audit history found.")
            
    with tab3:
        st.subheader("Active Guardrails")
        features = data.get("features", {})
        for feature, detail in features.items():
            status = "✅ Active" if detail.get("enabled") else "❌ Disabled"
            st.write(f"**{feature.title()}**: {status}")
