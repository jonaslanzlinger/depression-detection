# Implementation Plan: Fleet Health & Reliability Page

**Status:** ready to implement · **Author:** planning session 2026-07-09 · **Executor:** any Claude session with repo + VM access
**Scope:** ONE feature — a dashboard page that shows the live health and reliability history of the edge-node fleet, plus the small data-plumbing it needs. Nothing else.

---

## 0. Why this feature

Tonight's 4-node bring-up hit three symptoms with one root cause — **the system collects health signals but stores almost none of them**:

- Nodes publish status heartbeats every 30 s (RSSI, heap, uptime, mute) → only the *latest* is stored (overwritten in `iotsensing.nodes.telemetry`). No history ⇒ no way to see disconnects, RSSI drift, or crash-reboots.
- Button double-press publishes event markers to `nodes/{id}/marker` → **nobody consumes them at all**. They vanish.
- The user saw "only 3 of 4 online" and "No data received. Is the board active?" and had no page to answer "is my fleet actually healthy?"

A 30-day in-home study starts soon. This page is simultaneously the study babysitter and the reliability dataset for a journal paper (ACM TIOT). Design queries so raw data can also be exported/analyzed later.

---

## 1. Executor briefing — READ FIRST

### 1.1 Where things run

| Thing | Where |
|---|---|
| Repo | `github.com/brunobastosrodrigues/audio-depression-detection`, branch `main`. Commit directly to `main` (repo owner's explicit preference — no PRs). |
| Server stack | VM `192.168.1.16` (ssh `rodrigues` / pw `semsenha`), dir `~/audio-depression-detection`, docker compose. |
| Services touched | `node_registry_service` (python, paho-mqtt) and `dashboard_layer` (Streamlit, port 8084, LAN: http://192.168.1.16:8084). |
| MongoDB | container `mongodb`, auth from `~/audio-depression-detection/.env` (`MONGO_USER`/`MONGO_PASS`, authSource=admin). Shell: `docker exec mongodb mongosh --quiet -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin`. |
| MQTT | container name matches `mqtt`; creds `MQTT_USER`/`MQTT_PASS` from same `.env`. Subscribe test: `docker exec $(docker ps -qf name=mqtt) mosquitto_sub -h localhost -u "$MQTT_USER" -P "$MQTT_PASS" -t 'nodes/#' -v`. |
| Live fleet | 4× ReSpeaker Lite (`respeaker-10b41dd289a8`, `-10b41de9e460`, `-9070690c7e1c`, `-90706911c718`) + 1 XVF3800 running a Lite image (`respeaker-10b41de9817c`, network-only). All heartbeat every 30 s. |

### 1.2 Deploy workflow (containers have code BAKED — no bind mounts)

For each changed file, after committing to main:
```bash
ssh rodrigues@192.168.1.16   # pw semsenha
cd ~/audio-depression-detection && git pull origin main
# registry:
R=$(docker ps -qf name=node_registry)
docker cp data_ingestion_layer/node_registry_service.py $R:/app/node_registry_service.py
docker cp data_ingestion_layer/framework/node_registry.py $R:/app/framework/node_registry.py
docker restart $R
# dashboard:
D=$(docker ps -qf name=dashboard)
docker cp dashboard_layer/pages/12_Fleet_Health.py $D:/app/pages/12_Fleet_Health.py
docker restart $D    # Streamlit restart is instant; registry restart re-processes retained adverts (normal)
```
This hot-patch + commit pattern is the established practice in this repo. ALWAYS do both (commit AND docker cp) — the container image is only rebuilt occasionally.

### 1.3 Hard constraints — violations have bitten us already

1. **The registry container runs Python 3.9-family.** Do NOT use f-strings with nested same-type quotes (`f"{d["x"]}"` is a SyntaxError there) and no `match` statements. Use `f"{d['x']}"`.
2. **All timestamps naive UTC** — `datetime.now(timezone.utc)` when writing via pymongo is fine (Mongo stores UTC), but when COMPARING in Python, normalize: Mongo returns naive datetimes; never subtract aware from naive.
3. **Do NOT touch anything under `data_ingestion_layer/firmware/`** — a separate bench machine owns that tree and has unpushed local changes.
4. **Do not modify existing pages** except where this plan explicitly says so.
5. **Commit style:** conventional commits (`feat(dashboard): ...`), end body with `Co-Authored-By:` trailer for your model, push to `main` directly.
6. Streamlit page files auto-register by filename: `pages/12_Fleet_Health.py` → sidebar entry "Fleet Health". Do not add routing anywhere.
7. `plotly` IS available in the dashboard image (other pages use it). `pandas` available everywhere.

### 1.4 Files you will touch (verified to exist, read each before editing)

- `data_ingestion_layer/node_registry_service.py` (~150 lines) — MQTT consumer service. Already subscribes `nodes/+/capabilities` and `nodes/+/status` (method `handle_status`, added 2026-07-09, updates `iotsensing.nodes` + bridges to `boards`).
- `data_ingestion_layer/framework/node_registry.py` — `NodeRegistry` class (`register`, `touch`, `get`, `all`).
- `dashboard_layer/pages/10_Edge_Nodes.py` — reference for style/conventions (`@st.cache_data(ttl=10)`, `get_client()`, refresh button pattern). READ IT and imitate its structure.
- `dashboard_layer/utils/database.py` — `get_client()` singleton (env `MONGO_URI`), `get_database(mode)`, `render_mode_selector`.
- NEW: `dashboard_layer/pages/12_Fleet_Health.py`.

---

## 2. Part A — data plumbing (node_registry_service)

### A1. Persist status history

**New collection:** `iotsensing.node_status_history` (global DB, NOT mode-isolated — node health is mode-independent, same as `iotsensing.nodes`).

Document shape (one per received status message):
```json
{
  "node_id": "respeaker-10b41dd289a8",
  "ts": ISODate,            // server receive time, not node time
  "online": true,            // false comes from the broker LWT on ungraceful death
  "rssi": -70,
  "free_heap": 6862228,
  "uptime_s": 2286,
  "muted": false,
  "mode": "segments"
}
```

Implementation: in `handle_status(...)` (it already parses the payload into a `telemetry` dict), additionally `insert_one` into `node_status_history`. Wrap in try/except that only logs — a history write failure must NEVER break the existing touch/bridge behavior.

**Volume/retention:** 5 nodes × 2880 msg/day ≈ 14.4k docs/day, trivial. Still, create a **TTL index (90 days)** and a compound query index. Create indexes idempotently at service startup (in `NodeRegistryService.__init__`), NOT per message:
```python
hist = self.mongo_client["iotsensing"]["node_status_history"]
hist.create_index([("node_id", 1), ("ts", -1)])
hist.create_index("ts", expireAfterSeconds=90 * 24 * 3600)
```
(`create_index` is idempotent — safe on every boot.)

### A2. Consume event markers

**Subscribe** to `nodes/+/marker` (add alongside the existing two subscriptions in `on_connect`, and a topic route in `on_message` — follow the exact pattern `handle_status` uses; topic segment is the authoritative node identity, ignore payload `node_id`).

**New collection:** `iotsensing.node_markers`:
```json
{ "node_id": "...", "ts": ISODate, "uptime_s": 1234, "muted": false, "payload": { ...original... } }
```
Index `[("node_id",1),("ts",-1)]`, no TTL (markers are precious ground-truth annotations for the study — never expire them).

Firmware publishes marker payloads like `{"node_id":"...","uptime_s":123,"muted":false}` (see `offload_app.c`, but don't open firmware files — trust this shape and store the whole payload defensively under `payload`).

### A3. Detect reboots (derived, no schema change)

A node crash/reboot appears as `uptime_s` decreasing between consecutive status messages. Do NOT compute this in the registry — it's derivable at query time (Part B) and keeping the writer dumb keeps it reliable.

### A4. Registry unit-style check (no test framework needed here)

After deploying, verify from the VM:
```bash
source ~/audio-depression-detection/.env
docker exec mongodb mongosh --quiet -u "$MONGO_USER" -p "$MONGO_PASS" --authenticationDatabase admin --eval '
const h = db.getSiblingDB("iotsensing").node_status_history;
print("history docs:", h.countDocuments({}));
print("last:", JSON.stringify(h.find().sort({ts:-1}).limit(1).toArray()[0]));'
```
Expect count to grow by ~5 every 30 s. For markers: double-press a board button is NOT available to you — instead publish a synthetic marker and verify it lands:
```bash
M=$(docker ps -qf name=mqtt)
docker exec $M mosquitto_pub -h localhost -u "$MQTT_USER" -P "$MQTT_PASS" \
  -t "nodes/respeaker-test-marker/marker" -m '{"uptime_s":1,"muted":false}'
# ... then check iotsensing.node_markers, then delete that test doc.
```

---

## 3. Part B — the dashboard page (`pages/12_Fleet_Health.py`)

### B1. Page skeleton & conventions

Copy the structural conventions of `pages/10_Edge_Nodes.py` exactly: module docstring, `st.set_page_config` if that page has it (check), title with emoji (use 🩺 or 📡), a caption explaining data sources, `@st.cache_data(ttl=15, show_spinner=False)` loaders taking only hashable args, and a manual "🔄 Refresh" button that `.clear()`s the caches. All Mongo access via `from utils.database import get_client`.

Time-window selector at the top: `st.selectbox("Window", ["1 h", "6 h", "24 h", "7 d", "30 d"], index=2)` → map to a `timedelta`. Every chart/table below respects it.

### B2. Section 1 — Fleet summary tiles (top row)

`st.columns(5)` metrics:
1. **Nodes online** — `n_online / n_total`. Online = latest history doc per node has `online: true` AND `ts` within 2× heartbeat interval + slack (use **90 s**). Do NOT reuse the old 5-minute rule; with 30 s heartbeats, 90 s is the honest threshold.
2. **Weakest RSSI** — min of latest per-node RSSI, with the node id short-suffix as delta text (e.g. `…e460`). Color: `st.metric` delta_color="inverse" so more negative shows red-ish.
3. **Reboots (window)** — total uptime-reset count across fleet (see B5 query).
4. **Muted now** — count of nodes whose latest `muted` is true.
5. **Markers (window)** — count from `node_markers`.

### B3. Section 2 — per-node cards

One `st.container(border=True)` per node (iterate `iotsensing.nodes`, join with latest history). Layout per card: `st.columns([2,1,1,1,1])`:
- Node id (code-formatted) + hardware string from `capabilities.hardware` + 🟢/🔴/🔕 (online/offline/muted) emoji status.
- RSSI now + **sparkline** of RSSI over the window (`st.line_chart` on a small df is fine; if you want compactness use plotly `go.Scatter` with `height=120`, hidden axes).
- Free-heap sparkline (leak detection — a monotonic downtrend across hours is a firmware leak; that's exactly what this chart is for).
- Uptime (humanize: `f"{d}d {h}h {m}m"`).
- Last seen (`X s ago`, red text if > 90 s).

### B4. Section 3 — reliability timeline

A plotly **availability strip chart**: y = node_id (categorical), x = time; draw a green segment per contiguous online run and red gaps where heartbeats are missing (gap = consecutive history docs > 90 s apart) or `online:false` was recorded. Build segments in pandas: per node, sort by ts, compute `gap = ts.diff() > 90s`, cumsum into run ids, aggregate run start/end. Use `plotly.express.timeline` (`px.timeline(df, x_start=..., x_end=..., y="node_id", color="state", color_discrete_map={"online":"#16a34a","offline":"#dc2626"})`).

Overlay **markers** as vertical annotations or a scatter row: `node_markers` in window as diamond symbols on the corresponding node row. Overlay **reboots** (B5) as ⚡ scatter points.

### B5. Section 4 — reboot & disconnect table

Aggregation for reboots — run in pandas after fetching the window's history (simpler and testable, avoids a hairy `$setWindowFields` dependency on Mongo version):
```python
df = df.sort_values(["node_id", "ts"])
df["prev_uptime"] = df.groupby("node_id")["uptime_s"].shift()
reboots = df[df["uptime_s"] < df["prev_uptime"]]      # uptime went backwards ⇒ reboot
```
Table: node, reboot time, prior uptime (how long it had lived — humanized). Below it, a **disconnect table** from the gap analysis in B4 (node, gap start, duration). If both are empty: `st.success("No reboots or connectivity gaps in this window 🎉")` — that line is the daily go/no-go for the study.

### B6. Section 5 — data delivery per board

Segments actually delivered, per node per hour — from `iotsensing_live.raw_metrics` (mode-fixed to live; this page is not mode-switched, state that in a caption). One document per metric is written per segment, so count **distinct segment timestamps**:
```python
pipeline = [
  {"$match": {"timestamp": {"$gte": window_start}, "board_id": {"$ne": None}}},
  {"$group": {"_id": {"b": "$board_id", "t": "$timestamp"}}},                    # collapse metrics → segments
  {"$group": {"_id": {"b": "$_id.b", "h": {"$dateTrunc": {"date": "$_id.t", "unit": "hour"}}}, "n": {"$sum": 1}}},
]
```
(If `$dateTrunc` errors on the deployed Mongo version, fall back to truncating in pandas.) Render as a plotly stacked bar (x=hour, color=board). Caption must explain: *zero segments ≠ broken — segments only exist when the enrolled speaker talks near that board.*

### B7. Section 6 — markers list

Plain `st.dataframe` of `node_markers` in window (ts, node, muted-at-time), newest first, with a caption that these are the participant's button annotations.

### B8. Empty-state handling (IMPORTANT)

The page must render usefully with zero history (fresh install): every section checks for empty frames and shows an `st.info` explaining what will appear and where the data comes from. No stack traces on empty collections — this WILL be the first thing the user opens tomorrow morning.

---

## 4. Part C — one ride-along fix (explicitly in scope)

`pages/10_Edge_Nodes.py` computes online/stale from `last_seen` with a 5-minute threshold. Change ONLY the threshold to 90 s and, if the page displays telemetry, prefer `telemetry.online`. Nothing else on that page.

---

## 5. Acceptance criteria (verify each, in order)

1. `node_status_history` grows ~5 docs/30 s; TTL + compound indexes exist (`getIndexes()`).
2. Synthetic marker lands in `node_markers` (then delete the test doc).
3. Registry restart is clean: `docker logs` shows all three subscriptions, no exceptions in 5 minutes of running.
4. Existing behavior intact after restart: `iotsensing.nodes` telemetry still refreshes (watch `last_seen` advance), `iotsensing_live.boards.is_active` still updates.
5. Dashboard: new "Fleet Health" sidebar entry; page renders < 3 s on 24 h window; shows 5 nodes; tiles plausible (online count matches `mosquitto_sub` reality).
6. Pull a node's power (ask the user, or wait) OR simulate: the strip chart + summary must show the gap within ~2 min. If no hardware access, at minimum verify the gap logic against a synthetic hole: temporarily insert two history docs 10 min apart for a fake node id, confirm a red segment renders, delete the fake docs.
7. Empty-window sanity: 1 h window shortly after deploy renders without errors.
8. All changes committed to `main` AND hot-patched into both containers (registry, dashboard).
9. Add a row to `docs/plans/FLEET_HEALTH_PLAN.md` § "Execution log" (below) summarizing what was done and any deviations.

## 6. Explicitly OUT of scope — do not do these

- No auth on the dashboard (separate task).
- No firmware changes of any kind (`data_ingestion_layer/firmware/**` is owned by another machine).
- No changes to `voice_metrics`, `analysis_layer`, `temporal_context_modeling_layer`.
- No alerting/notifications (future).
- No `audio_quality_metrics` widget fix on the Boards page (separate task).
- No changes to heartbeat cadence or any MQTT publishing.

## 7. Execution log

| Date | Executor | Result |
|---|---|---|
| 2026-07-09 | Claude Sonnet 5 | **Implemented in full, all 9 acceptance criteria verified.** Part A: `node_registry_service.py` now subscribes `nodes/+/marker`, writes `iotsensing.node_status_history` (TTL 90d, compound index) on every status heartbeat (best-effort, wrapped so a write failure can never break the existing touch/boards-bridge), and `iotsensing.node_markers` (no TTL). Commit `63e1d87`. Part B: new `dashboard_layer/pages/12_Fleet_Health.py` — summary tiles, per-node cards w/ RSSI+heap sparklines, plotly availability-strip timeline (online/offline runs, marker + reboot overlays), reboot/gap tables, per-hour segment-delivery chart, marker list; every section has an explicit empty-state branch. Part C: `10_Edge_Nodes.py` online threshold 300s→90s (one line, nothing else touched). Commit `2bb0409`. Both hot-patched into the running `node_registry` and `dashboard_layer` containers per §1.2. **Deviation from plan:** criterion #5's suggested verification (`curl` the page URL) does NOT actually execute page code — Streamlit serves an identical SPA shell for every path, confirmed by diffing `curl / ` vs `curl /Fleet_Health` (byte-identical). Verified instead by extracting the page's full data-pipeline (Mongo queries → pandas transforms → `fig.to_json()`) into a standalone script and running it inside the dashboard container against live data across two window sizes; this incidentally exercised two real edge cases the live fleet produced during testing (a node with zero history in-window, a brand-new node with no telemetry yet) with zero exceptions. Criterion #6 (gap detection) verified with the exact synthetic-two-docs-10-min-apart method the plan specifies; cleaned up after. Criterion #7 (empty window) verified with a future `window_start` forcing all five sections into their empty-state branch. Registry container's stdout is unbuffered-silent (`docker logs` shows nothing; pre-existing condition, `PYTHONUNBUFFERED` not set, unrelated to this change) — substituted direct Mongo/`docker inspect` checks (RestartCount 0, uptime growing, `last_seen`/`boards.is_active` continuing to update) as stronger evidence than log lines would have been anyway. **Note for the next executor:** the fleet grew from 5→6→7 nodes live during this work (unrelated boards being flashed concurrently) — the page and registry code make no assumption about fleet size, so this required no changes, but is worth knowing if reliability numbers look odd on first real review. Follow-up not in this plan's scope: registry `PYTHONUNBUFFERED` (would make future debugging much easier), `docker-compose.yml` restart policy audit (not needed here — zero restarts observed).|
