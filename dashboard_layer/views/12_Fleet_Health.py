"""Fleet Health page: live status and historical reliability of the edge-node fleet.

Data sources:
- `iotsensing.nodes` — latest capabilities/assignment/telemetry per node (node_registry_service).
- `iotsensing.node_status_history` — one doc per 30s heartbeat, TTL 90 days.
- `iotsensing.node_markers` — participant button double-press event markers (kept forever).
- `iotsensing_live.raw_metrics` — per-segment delivery (this page is fixed to LIVE mode; it is
  a fleet/hardware view, not a per-user research view like the other mode-switched pages).

This page is the deployment babysitter for the in-home study AND the reliability dataset for
the paper's evaluation section.
"""
import math
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta


def _nan_to_none(v):
    """pandas yields NaN for missing numeric cells; NaN crashes int()/formatting and
    displays as 'nan'. Normalize to None so downstream shows '—'."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v

from utils.database import get_client, get_database
from utils.theme import COLORS

st.title("🩺 Fleet Health & Reliability")
st.markdown(
    "Live status and historical reliability of the edge-node fleet: online/offline, signal "
    "strength, reboots, connectivity gaps, participant event markers, and data delivery. "
    "Fixed to **Live** mode (this is a hardware/deployment view, not a per-user research view)."
)

ONLINE_WINDOW_S = 90  # 3x the 30s heartbeat interval + slack

WINDOW_OPTIONS = {
    "1 h": timedelta(hours=1),
    "6 h": timedelta(hours=6),
    "24 h": timedelta(hours=24),
    "7 d": timedelta(days=7),
    "30 d": timedelta(days=30),
}

def _to_naive_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def _humanize_seconds(seconds):
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return "—"
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)

# ------------------------------------------------------------------------------- controls
top_l, top_r = st.columns([3, 1])
with top_l:
    window_label = st.selectbox("Window", list(WINDOW_OPTIONS.keys()), index=2)
with top_r:
    st.markdown("&nbsp;")  # vertical alignment spacer to match selectbox height
    if st.button("🔄 Refresh"):
        st.cache_data.clear()

window_delta = WINDOW_OPTIONS[window_label]
now = datetime.utcnow()
window_start = now - window_delta

# ------------------------------------------------------------------------------- loaders
@st.cache_data(ttl=15, show_spinner=False)
def load_nodes():
    return list(get_client()["iotsensing"]["nodes"].find({}, {"_id": 0}))

@st.cache_data(ttl=15, show_spinner=False)
def load_history(window_start_iso: str):
    window_start_dt = datetime.fromisoformat(window_start_iso)
    docs = list(
        get_client()["iotsensing"]["node_status_history"]
        .find({"ts": {"$gte": window_start_dt}}, {"_id": 0})
        .sort("ts", 1)
    )
    return docs

@st.cache_data(ttl=15, show_spinner=False)
def load_markers(window_start_iso: str):
    window_start_dt = datetime.fromisoformat(window_start_iso)
    docs = list(
        get_client()["iotsensing"]["node_markers"]
        .find({"ts": {"$gte": window_start_dt}}, {"_id": 0})
        .sort("ts", -1)
    )
    return docs

@st.cache_data(ttl=15, show_spinner=False)
def load_segment_counts(window_start_iso: str):
    """Distinct-segment count per board per hour, LIVE mode only. One raw_metrics doc is
    written per METRIC, so a segment (one utterance) yields many docs at the same
    (board_id, timestamp) -- collapse those before counting, then bucket by hour."""
    window_start_dt = datetime.fromisoformat(window_start_iso)
    db = get_database("live")
    pipeline = [
        {"$match": {"timestamp": {"$gte": window_start_dt}, "board_id": {"$ne": None}}},
        {"$group": {"_id": {"b": "$board_id", "t": "$timestamp"}}},
        {"$project": {"board_id": "$_id.b", "timestamp": "$_id.t"}},
    ]
    segs = list(db["raw_metrics"].aggregate(pipeline))
    return segs

nodes = load_nodes()
history_docs = load_history(window_start.isoformat())
marker_docs = load_markers(window_start.isoformat())
segment_docs = load_segment_counts(window_start.isoformat())

if not nodes:
    st.info(
        "No edge nodes registered yet. A node appears here once it publishes a capability "
        "advertisement to `nodes/{id}/capabilities` and the registry negotiates an assignment. "
        "See the **Edge Nodes** page for registration details."
    )
    st.stop()

hist_df = pd.DataFrame(history_docs)
if not hist_df.empty:
    hist_df["ts"] = hist_df["ts"].apply(_to_naive_utc)
    hist_df = hist_df.sort_values(["node_id", "ts"])

marker_df = pd.DataFrame(marker_docs)
if not marker_df.empty:
    marker_df["ts"] = marker_df["ts"].apply(_to_naive_utc)

node_ids = [n.get("node_id", "?") for n in nodes]

# ------------------------------------------------------------------------------- latest-per-node
def _latest_for(node_id):
    if hist_df.empty:
        return None
    rows = hist_df[hist_df["node_id"] == node_id]
    return rows.iloc[-1] if not rows.empty else None

online_count = 0
weakest_rssi = None
weakest_node = None
muted_count = 0
node_summaries = []
for n in nodes:
    nid = n.get("node_id", "?")
    latest = _latest_for(nid)
    last_seen = _to_naive_utc(n.get("last_seen"))
    age = (now - last_seen).total_seconds() if last_seen else None
    is_online = age is not None and age <= ONLINE_WINDOW_S
    online_count += int(is_online)

    rssi = _nan_to_none(latest["rssi"]) if latest is not None else None
    if rssi is not None and (weakest_rssi is None or rssi < weakest_rssi):
        weakest_rssi = rssi
        weakest_node = nid

    muted = bool(latest["muted"]) if latest is not None and latest.get("muted") is not None else False
    muted_count += int(muted)

    node_summaries.append({
        "node_id": nid,
        "hardware": (n.get("capabilities") or {}).get("hardware", "?"),
        "is_online": is_online,
        "muted": muted,
        "rssi": rssi,
        "free_heap": _nan_to_none(latest["free_heap"]) if latest is not None else None,
        "uptime_s": _nan_to_none(latest["uptime_s"]) if latest is not None else None,
        "age_s": age,
    })

reboot_count = 0
gap_events = []  # filled below in section 4, reused by the summary tile
if not hist_df.empty:
    tmp = hist_df.copy()
    tmp["prev_uptime"] = tmp.groupby("node_id")["uptime_s"].shift()
    reboot_count = int((tmp["uptime_s"] < tmp["prev_uptime"]).sum())

# ------------------------------------------------------------------------------- section 1: tiles
st.subheader("Fleet summary")
t1, t2, t3, t4, t5 = st.columns(5)
t1.metric("Nodes online", f"{online_count} / {len(nodes)}")
t2.metric(
    "Weakest signal",
    f"{weakest_rssi} dBm" if weakest_rssi is not None else "—",
    delta=f"…{weakest_node[-6:]}" if weakest_node else None,
    delta_color="off",
)
t3.metric(f"Reboots ({window_label})", reboot_count)
t4.metric("Muted now", muted_count)
t5.metric(f"Markers ({window_label})", len(marker_docs))

st.divider()

# ------------------------------------------------------------------------------- section 2: per-node cards
st.subheader("Per-node status")
for summary in node_summaries:
    nid = summary["node_id"]
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
        with c1:
            status_icon = "🔕" if summary["muted"] else ("🟢" if summary["is_online"] else "🔴")
            st.markdown(f"**{status_icon} `{nid}`**")
            st.caption(summary["hardware"])
        with c2:
            st.metric("RSSI", f"{summary['rssi']} dBm" if summary["rssi"] is not None else "—")
            node_hist = hist_df[hist_df["node_id"] == nid] if not hist_df.empty else pd.DataFrame()
            if not node_hist.empty and node_hist["rssi"].notna().any():
                st.line_chart(node_hist.set_index("ts")["rssi"], height=100, use_container_width=True)
        with c3:
            heap_mb = summary["free_heap"] / (1024 * 1024) if summary["free_heap"] else None
            st.metric("Free heap", f"{heap_mb:.2f} MB" if heap_mb is not None else "—")
            if not node_hist.empty and node_hist["free_heap"].notna().any():
                st.line_chart(node_hist.set_index("ts")["free_heap"], height=100, use_container_width=True)
        with c4:
            st.metric("Uptime", _humanize_seconds(summary["uptime_s"]))
        with c5:
            age_label = f"{int(summary['age_s'])}s ago" if summary["age_s"] is not None else "never"
            st.metric("Last seen", age_label)
            if summary["age_s"] is not None and summary["age_s"] > ONLINE_WINDOW_S:
                st.caption(":red[stale]")

if hist_df.empty:
    st.info(
        "No status history in this window yet. History accumulates as nodes send their "
        "30s heartbeats — sparklines and the timeline below will populate shortly."
    )

st.divider()

# ------------------------------------------------------------------------------- section 3: reliability timeline
st.subheader("Reliability timeline")

if hist_df.empty:
    st.info("No status history in this window yet — the timeline needs at least two heartbeats per node.")
else:
    segments = []
    for nid, grp in hist_df.groupby("node_id"):
        grp = grp.sort_values("ts").reset_index(drop=True)
        if len(grp) == 1:
            segments.append({
                "node_id": nid, "start": grp.loc[0, "ts"], "end": grp.loc[0, "ts"] + timedelta(seconds=1),
                "state": "online" if grp.loc[0, "online"] else "offline",
            })
            continue
        gap = grp["ts"].diff().dt.total_seconds() > ONLINE_WINDOW_S
        run_id = gap.cumsum()
        for _, run in grp.groupby(run_id):
            state = "online" if bool(run["online"].iloc[-1]) else "offline"
            segments.append({
                "node_id": nid, "start": run["ts"].iloc[0], "end": run["ts"].iloc[-1], "state": state,
            })
        # gaps between runs (connectivity holes)
        run_bounds = grp.groupby(run_id)["ts"].agg(["first", "last"])
        for i in range(len(run_bounds) - 1):
            gap_start = run_bounds.iloc[i]["last"]
            gap_end = run_bounds.iloc[i + 1]["first"]
            gap_events.append({
                "node_id": nid, "start": gap_start, "end": gap_end,
                "duration_s": (gap_end - gap_start).total_seconds(),
            })
            segments.append({"node_id": nid, "start": gap_start, "end": gap_end, "state": "offline"})

    seg_df = pd.DataFrame(segments)
    # px.timeline needs distinct start/end; zero-width bars are invisible, pad by 1s.
    seg_df.loc[seg_df["start"] == seg_df["end"], "end"] += timedelta(seconds=1)

    fig = px.timeline(
        seg_df, x_start="start", x_end="end", y="node_id", color="state",
        color_discrete_map={"online": COLORS["success"], "offline": COLORS["danger"]},
    )
    fig.update_yaxes(categoryorder="array", categoryarray=sorted(node_ids))
    fig.update_layout(height=120 + 40 * len(node_ids), showlegend=True, legend_title_text="")

    if not marker_df.empty:
        fig.add_trace(go.Scatter(
            x=marker_df["ts"], y=marker_df["node_id"], mode="markers",
            marker=dict(symbol="diamond", size=11, color=COLORS["info"], line=dict(width=1, color="white")),
            name="event marker",
        ))

    reboot_rows = []
    if not hist_df.empty:
        tmp = hist_df.copy()
        tmp["prev_uptime"] = tmp.groupby("node_id")["uptime_s"].shift()
        reboot_rows = tmp[tmp["uptime_s"] < tmp["prev_uptime"]]
        if not reboot_rows.empty:
            fig.add_trace(go.Scatter(
                x=reboot_rows["ts"], y=reboot_rows["node_id"], mode="markers",
                marker=dict(symbol="star", size=13, color=COLORS["warning"], line=dict(width=1, color="white")),
                name="reboot",
            ))

    st.plotly_chart(fig, use_container_width=True)
    st.caption("🟢 online · 🔴 offline/gap · 🔷 event marker (button double-press) · ⭐ reboot detected")

st.divider()

# ------------------------------------------------------------------------------- section 4: reboot & disconnect tables
st.subheader("Reboots & connectivity gaps")
rc1, rc2 = st.columns(2)

with rc1:
    st.markdown("**Reboots**")
    if not hist_df.empty:
        tmp = hist_df.copy()
        tmp["prev_uptime"] = tmp.groupby("node_id")["uptime_s"].shift()
        reboots = tmp[tmp["uptime_s"] < tmp["prev_uptime"]][["node_id", "ts", "prev_uptime"]].copy()
        if not reboots.empty:
            reboots["Prior uptime"] = reboots["prev_uptime"].apply(_humanize_seconds)
            reboots = reboots.rename(columns={"node_id": "Node", "ts": "Reboot time"})
            st.dataframe(
                reboots[["Node", "Reboot time", "Prior uptime"]].sort_values("Reboot time", ascending=False),
                use_container_width=True, hide_index=True,
            )
        else:
            reboots = pd.DataFrame()
    else:
        reboots = pd.DataFrame()
    if reboots.empty:
        st.success("No reboots in this window 🎉" if not hist_df.empty else "No history yet.")

with rc2:
    st.markdown("**Connectivity gaps**")
    if gap_events:
        gap_df = pd.DataFrame(gap_events)
        gap_df["Gap start"] = gap_df["start"]
        gap_df["Duration"] = gap_df["duration_s"].apply(_humanize_seconds)
        st.dataframe(
            gap_df.rename(columns={"node_id": "Node"})[["Node", "Gap start", "Duration"]]
            .sort_values("Gap start", ascending=False),
            use_container_width=True, hide_index=True,
        )
    else:
        st.success("No connectivity gaps in this window 🎉" if not hist_df.empty else "No history yet.")

st.divider()

# ------------------------------------------------------------------------------- section 5: data delivery
st.subheader("Data delivery (segments/hour, live mode)")
st.caption(
    "Segments only exist when the enrolled speaker talks near that board — zero segments in "
    "an hour does not mean the board is broken, it means nobody spoke near it."
)
if not segment_docs:
    st.info("No segments delivered in this window yet.")
else:
    seg_df2 = pd.DataFrame(segment_docs)
    seg_df2["timestamp"] = seg_df2["timestamp"].apply(_to_naive_utc)
    seg_df2["hour"] = seg_df2["timestamp"].dt.floor("h")
    hourly = seg_df2.groupby(["hour", "board_id"]).size().reset_index(name="segments")
    fig2 = px.bar(hourly, x="hour", y="segments", color="board_id", barmode="stack")
    fig2.update_layout(height=350, legend_title_text="Board")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ------------------------------------------------------------------------------- section 6: markers list
st.subheader("Event markers")
st.caption("Participant button double-presses: ground-truth annotations for the study.")
if marker_df.empty:
    st.info(
        "No event markers in this window. A participant double-pressing a node's button "
        "publishes one here (see the firmware button gestures)."
    )
else:
    display_df = marker_df.copy()
    display_df["Muted at time"] = display_df["muted"].apply(lambda m: "🔕" if m else "")
    st.dataframe(
        display_df.rename(columns={"node_id": "Node", "ts": "Time"})[["Time", "Node", "Muted at time"]]
        .sort_values("Time", ascending=False),
        use_container_width=True, hide_index=True,
    )
