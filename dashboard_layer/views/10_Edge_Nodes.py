"""Edge Nodes page: registered ESP32-S3 nodes, their advertised capabilities, and the
negotiated offload assignment (read from the global node registry, iotsensing.nodes)."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from utils.database import get_client, render_mode_selector

render_mode_selector()

st.title("🔌 Edge Nodes")
st.markdown(
    "Registered edge nodes (ESP32-S3), their advertised capabilities, and the offload "
    "assignment the server negotiated for each. Nodes register by publishing to "
    "`nodes/{id}/capabilities`; the node_registry_service replies on `nodes/{id}/config`."
)

ONLINE_WINDOW_S = 90  # 3x the 30s heartbeat interval + slack (was 300s/5min: with 30s
                       # heartbeats that stale threshold made healthy nodes read "offline")

@st.cache_data(ttl=10, show_spinner=False)
def load_nodes():
    return list(get_client()["iotsensing"]["nodes"].find({}, {"_id": 0}))

if st.button("🔄 Refresh"):
    load_nodes.clear()

nodes = load_nodes()
if not nodes:
    st.info(
        "No edge nodes registered yet. A node appears here once it publishes a capability "
        "advertisement to `nodes/{id}/capabilities` and the registry negotiates an assignment."
    )
    st.stop()

def _to_naive_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

now = datetime.utcnow()
rows = []
online = 0
for n in nodes:
    caps = n.get("capabilities", {}) or {}
    prov = caps.get("provides", {}) or {}
    asg = n.get("assignment", {}) or {}
    last_seen = _to_naive_utc(n.get("last_seen"))
    age = (now - last_seen).total_seconds() if last_seen else None
    is_online = age is not None and age <= ONLINE_WINDOW_S
    online += int(is_online)
    rows.append({
        "Node": n.get("node_id", "?"),
        "Status": "🟢 online" if is_online else "⚪ stale",
        "Hardware": caps.get("hardware", "?"),
        "FW": caps.get("firmware", "?"),
        "Mode": asg.get("mode", "?"),
        "VAD": "✓" if prov.get("vad") else "",
        "AEC": "✓" if prov.get("aec") else "",
        "DoA": "✓" if prov.get("doa") else "",
        "Offloaded features": ", ".join(asg.get("features", []) or []) or "—",
        "Last seen (s ago)": int(age) if age is not None else "—",
    })

c1, c2, c3, c4 = st.columns(4)
c1.metric("Registered nodes", len(nodes))
c2.metric("Online", online)
mode_counts = pd.Series([r["Mode"] for r in rows]).value_counts().to_dict()
c3.metric("Feature offload", mode_counts.get("features", 0))
c4.metric("Raw audio", mode_counts.get("raw", 0))

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.subheader("Node detail")
selected = st.selectbox("Node", [n.get("node_id", "?") for n in nodes])
node = next((n for n in nodes if n.get("node_id") == selected), None)
if node:
    left, right = st.columns(2)
    with left:
        st.caption("Advertised capabilities")
        st.json(node.get("capabilities", {}))
    with right:
        st.caption("Negotiated assignment")
        st.json(node.get("assignment", {}))
