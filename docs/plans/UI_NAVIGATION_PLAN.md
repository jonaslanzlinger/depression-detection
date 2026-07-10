# Implementation Plan: Dashboard Navigation & Information Architecture

**Status:** ready to implement · **Author:** planning session (Opus) 2026-07-09 · **Executor:** Claude Sonnet 5
**Scope decision (from the repo owner):** *Regroup the sidebar into sections; fix naming; add a proper landing page. Do NOT rewrite the 12 pages' content.* Primary user during the study = **the operator (you)**.

---

## 0. Why

The dashboard has **12 flat sidebar entries in filename order**, mixing three audiences with no hierarchy: a participant-facing "Your Wellness Overview" sits next to engineer-facing "Gatekeeper Decisions" and "Edge Nodes". Three pages cover the same hardware fleet (`Boards`, `Edge Nodes`, `Fleet Health`); three cover the same scores (`Overview`, `Indicators`, `Trends`). Names disagree across file / sidebar / page title. Result: no one can tell where to click.

This plan does NOT restyle charts or merge pages. It **groups the sidebar into labelled sections, makes naming consistent, and gives the operator a useful landing page** — the highest confusion-drop per unit of effort.

---

## 1. Executor briefing — READ FIRST

### 1.1 Environment (same as the Fleet Health plan)

| Thing | Where |
|---|---|
| Repo | `github.com/brunobastosrodrigues/audio-depression-detection`, branch `main`. Commit directly to `main` (owner's preference, no PRs). |
| Server | VM `192.168.1.16` (ssh `rodrigues` / pw `semsenha`), `~/audio-depression-detection`, docker compose. |
| Service | ONLY `dashboard_layer` (Streamlit, port 8084, http://192.168.1.16:8084). No other service is touched. |
| Streamlit | **1.55.0** — has the modern `st.navigation` + `st.Page` API (needs ≥1.36; confirmed present). |
| Entry point | `dashboard_layer/Home.py` (`streamlit run Home.py`, see Dockerfile). Currently does NOT use `st.navigation` — it relies on Streamlit's automatic `pages/` discovery (flat) + a manual card grid. |

### 1.2 Deploy workflow (code is BAKED into the image — no bind mounts)

After committing to main:
```bash
ssh rodrigues@192.168.1.16    # pw semsenha
cd ~/audio-depression-detection && git pull origin main
D=$(docker ps -qf name=dashboard)
docker cp dashboard_layer/Home.py     $D:/app/Home.py
docker cp dashboard_layer/pages/.      $D:/app/pages/     # copies the whole pages dir contents
docker restart $D
sleep 8 && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8084 -m 10
```

### 1.3 HARD CONSTRAINTS — read every line, these have bitten us

1. **THE LANDMINE — `st.set_page_config` must be removed from ALL 12 pages.** Under `st.navigation`, the entry (`Home.py`) calls `st.set_page_config` ONCE; then `pg.run()` executes the selected page's code *in the same script run*. If that page ALSO calls `st.set_page_config`, Streamlit raises `StreamlitSetPageConfigMustBeFirstCommandError` and the page shows a red crash box. Every page currently calls it. After your change, `grep -rl "st.set_page_config" dashboard_layer/pages/` MUST return **nothing**. This is the #1 way to break the app.
2. **`curl`-ing a page URL proves nothing.** Streamlit serves a byte-identical SPA shell for every path (verified last session: `curl /` == `curl /Fleet_Health`). HTTP 200 only means the server is up, not that a page runs. Verify via `docker logs` (Streamlit prints page exceptions there) + the smoke script in §5.
3. **Do NOT rewrite page CONTENT.** You remove the `set_page_config` block from each page and nothing else in the 12 pages (the in-page `st.title(...)`, mode/user selectors, all logic stay exactly as-is). The landing page (`Home.py` body) is NOT one of the 12 — reworking it is in scope.
4. **Keep filenames.** Under `st.navigation`, the `NN_` numeric prefixes no longer control order (the nav dict does), and pages are referenced by path. Do NOT rename page files — it's needless churn and breaks any deep links.
5. **Do not touch** `data_ingestion_layer/**` (firmware + services owned elsewhere), or any non-dashboard service.
6. Commit style: conventional commits, `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, push to `main`.
7. `plotly`, `pandas` available in the image. `utils.database.get_client`, `utils.theme.COLORS` exist and are used by `pages/12_Fleet_Health.py` — mirror it.

### 1.4 How `st.navigation` changes behaviour (know this before you start)

- When you call `st.navigation(...)`, Streamlit **stops auto-listing** `pages/*.py`. ONLY pages you pass to `st.navigation` appear. So every page (and the Home landing) must be listed explicitly — nothing double-appears, nothing is missed silently.
- `st.Page(path, title=, icon=, default=, url_path=)`: `title` is BOTH the sidebar label AND the browser-tab title for that page. **This is how naming becomes consistent centrally** — you set the label once here; you do NOT need to edit each page's in-page `st.title()`.
- Section grouping: pass a **dict** `{ "Section name": [st.Page(...), ...] }`. Streamlit renders each key as a non-clickable sidebar header with its pages beneath. Dict order = display order.
- The mode selector (`render_mode_selector`) and user selector are called *inside each page* today (11 of 12 pages call the mode selector). **Leave those calls alone** — they render into the sidebar below the nav and keep working. Do not centralize them (that would mean editing every page = scope creep + risk). The Home landing keeps calling them too.
- Session state persists across pages, and the default page runs first on app open, so `system_mode` is initialised before navigation.

---

## 2. Target information architecture (DECIDED — implement exactly this)

Sidebar, top-to-bottom. `path` is relative to `dashboard_layer/`. Titles/icons are the FINAL consistent names.

| Order | Section | Sidebar label (st.Page title) | icon | file path | notes |
|---|---|---|---|---|---|
| — | *(top, no section)* | **Home** | 🏠 | `pages/00_Home.py` | NEW file (Part B). `default=True`. |
| 1 | **My Wellbeing** | Overview | 💚 | `pages/1_Overview.py` | |
| 2 | My Wellbeing | Indicators | 📊 | `pages/2_Indicators.py` | |
| 3 | My Wellbeing | Trends | 📈 | `pages/3_Trends.py` | |
| 4 | My Wellbeing | Self-Report | 📝 | `pages/4_Self_Report.py` | |
| 5 | **Fleet** | Fleet Health | 🩺 | `pages/12_Fleet_Health.py` | |
| 6 | Fleet | Boards & Rooms | 📡 | `pages/5_Boards.py` | |
| 7 | Fleet | Edge Nodes | 🔌 | `pages/10_Edge_Nodes.py` | |
| 8 | **Admin** | Users & Enrollment | 👥 | `pages/8_User_Management.py` | |
| 9 | Admin | Data Tools | 🔧 | `pages/7_Data_Tools.py` | |
| 10 | Admin | Scene Analysis | 🔬 | `pages/9_Scene_Forensics.py` | |
| 11 | Admin | Settings | ⚙️ | `pages/6_Settings.py` | |
| 12 | Admin | Research Validation | 🧪 | `pages/11_Research_Validation.py` | |

Every icon is distinct (no clashes). This mapping is final; don't editorialize.

> Operator-primary note: the owner picked this section order (Wellbeing first) in the approved mock. Because the operator is the primary user, the **Home landing** (Part B) leads with a fleet-status strip so fleet health is visible on open regardless of section order. If the owner later wants the **Fleet** section physically first, that's a one-line swap of dict keys — leave a comment saying so.

---

## 3. Part A — convert `Home.py` into the navigation entry

Replace `Home.py` ENTIRELY with a thin controller. It must: set page config once, ensure indexes once, define the sections, run navigation. NO content, NO selectors (those live in the landing/pages).

```python
"""IHearYou dashboard entry point: defines the grouped navigation and runs the
selected page. Page content lives in pages/*.py; the landing is pages/00_Home.py."""
import streamlit as st
from utils.setup_db import setup_indexes

st.set_page_config(page_title="IHearYou", page_icon="🧠", layout="wide")


@st.cache_resource(show_spinner=False)
def _ensure_indexes_once():
    try:
        setup_indexes()
    except Exception as e:
        print(f"Index setup failed (expected if DB not ready): {e}")
    return True


_ensure_indexes_once()

pages = {
    "": [  # ungrouped, appears at the very top
        st.Page("pages/00_Home.py", title="Home", icon="🏠", default=True),
    ],
    "My Wellbeing": [
        st.Page("pages/1_Overview.py",     title="Overview",    icon="💚"),
        st.Page("pages/2_Indicators.py",   title="Indicators",  icon="📊"),
        st.Page("pages/3_Trends.py",       title="Trends",      icon="📈"),
        st.Page("pages/4_Self_Report.py",  title="Self-Report", icon="📝"),
    ],
    # To put Fleet above Wellbeing (operator-first), move this block above "My Wellbeing".
    "Fleet": [
        st.Page("pages/12_Fleet_Health.py", title="Fleet Health",   icon="🩺"),
        st.Page("pages/5_Boards.py",        title="Boards & Rooms", icon="📡"),
        st.Page("pages/10_Edge_Nodes.py",   title="Edge Nodes",     icon="🔌"),
    ],
    "Admin": [
        st.Page("pages/8_User_Management.py",     title="Users & Enrollment",  icon="👥"),
        st.Page("pages/7_Data_Tools.py",          title="Data Tools",          icon="🔧"),
        st.Page("pages/9_Scene_Forensics.py",     title="Scene Analysis",      icon="🔬"),
        st.Page("pages/6_Settings.py",            title="Settings",            icon="⚙️"),
        st.Page("pages/11_Research_Validation.py",title="Research Validation", icon="🧪"),
    ],
}

st.navigation(pages).run()
```

Notes:
- `st.Page` validates that each path exists at construction — a typo'd path throws immediately (good, cheap check).
- Do NOT call `render_mode_selector` / `render_user_selector` here — they run inside the pages/landing.
- The empty-string section key `""` renders "Home" with no header above it. If your Streamlit build dislikes an empty key, use a single space `" "`; if it still shows a stray header, instead make Home a top-level `st.Page` by passing a **list** for the first group is not supported — keep the dict; the empty key is the documented idiom. Verify visually.

## 4. Part B — create `pages/00_Home.py` (operator-first landing)

Move the CURRENT `Home.py` body here, with three changes:
1. **Delete** its `st.set_page_config(...)` call (the entry owns it now).
2. **Delete** the entire "Quick Navigation" card grid (old lines ~296-409) — the grouped sidebar replaces it; two nav systems was part of the confusion.
3. **Prepend an operator fleet-status strip** at the very top of the main content (right after the mode/user selector sidebar setup, before the wellbeing overview). It mirrors `pages/12_Fleet_Health.py`'s loaders:

```python
from datetime import datetime, timezone, timedelta
from utils.database import get_client

ONLINE_WINDOW_S = 90

def _fleet_strip():
    ic = get_client()["iotsensing"]
    nodes = list(ic["nodes"].find({}, {"_id": 0, "node_id": 1, "last_seen": 1, "telemetry": 1}))
    now = datetime.utcnow()
    online, weakest = 0, None
    for n in nodes:
        ls = n.get("last_seen")
        if ls is not None and getattr(ls, "tzinfo", None) is not None:
            ls = ls.astimezone(timezone.utc).replace(tzinfo=None)
        if ls is not None and (now - ls).total_seconds() <= ONLINE_WINDOW_S:
            online += 1
        r = (n.get("telemetry") or {}).get("rssi")
        if r is not None and (weakest is None or r < weakest):
            weakest = r
    since = now - timedelta(hours=24)
    segs = len(list(get_client()["iotsensing_live"]["raw_metrics"].aggregate([
        {"$match": {"timestamp": {"$gte": since}, "board_id": {"$ne": None}}},
        {"$group": {"_id": {"b": "$board_id", "t": "$timestamp"}}},
    ])))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nodes online", f"{online} / {len(nodes)}")
    c2.metric("Weakest signal", f"{weakest} dBm" if weakest is not None else "—")
    c3.metric("Segments (24h)", segs)
    c4.page_link("pages/12_Fleet_Health.py", label="Open Fleet Health →")

st.subheader("Fleet at a glance")
_fleet_strip()
st.divider()
# ... then the EXISTING wellbeing overview content (kept as-is) ...
```

Keep the existing "About This Project" / "Data Pipeline" expanders at the bottom. Do NOT expand scope beyond this — the wellbeing block stays exactly as it was.

## 5. Part C — strip `st.set_page_config` from all 12 pages

For EACH file in `pages/` that has it (all 12 — the grep in §1.3 lists them), delete only the `st.set_page_config(...)` call (usually a 1-line or small multi-line block near the top, right after imports). Change nothing else. Some pages may set `layout="centered"` — that's fine to drop; the entry's `layout="wide"` applies globally and is the better default for these data pages. After editing:

```bash
grep -rl "st.set_page_config" dashboard_layer/pages/   # MUST print nothing
```

---

## 6. Acceptance criteria (verify in order)

1. `grep -rl "st.set_page_config" dashboard_layer/pages/` prints nothing; exactly one `st.set_page_config` remains in the repo, in `Home.py`.
2. **Static smoke (before deploy):** `python -c "import ast; [ast.parse(open(f).read()) for f in __import__('glob').glob('dashboard_layer/**/*.py', recursive=True)]"` — all parse. Then a nav-construction check INSIDE the container (Streamlit must be importable): copy a tiny script that does `import streamlit as st` and constructs each `st.Page(path,...)` exactly as in Part A (this validates every path exists) — run it with `docker exec $D python /tmp/x.py`; it should exit 0. (It will warn "missing ScriptRunContext" — that's expected outside a real run; only a raised exception is a failure.)
3. Deploy per §1.2. `docker restart`, then `docker logs --since 60s $D` shows **no** `SetPageConfig`/`Traceback`/`Error` (ignore the known `use_container_width` FutureWarnings).
4. Open http://192.168.1.16:8084 — sidebar shows the three section headers (My Wellbeing / Fleet / Admin) with the right pages under each, plus Home at top. Labels match §2 exactly.
5. Click **every** page once; for each, `docker logs --since 20s $D` shows no traceback. (This is the real test — the SPA renders each page's Python only when visited. A leftover `set_page_config` on a page surfaces here as a crash box + a log error.)
6. Home landing shows the fleet strip (online count matches Fleet Health) + the wellbeing overview, and the old card grid is gone.
7. Deep-link test: open `http://192.168.1.16:8084/Fleet_Health` directly (fresh tab) — renders without a mode-init crash.
8. Update the Execution log (§8) with what you did and any deviations (e.g. the empty-section-key idiom if you had to adjust it).

## 7. OUT of scope — do not do these

- No chart restyling, no merging pages, no two-persona role switch (those were other options the owner did NOT pick).
- No renaming page files. No editing page content beyond removing `set_page_config`.
- No auth (separate task). No changes to any non-dashboard service or the firmware.
- No centralizing the mode/user selectors (leave each page's calls as-is).
- Do NOT touch `pages/12_Fleet_Health.py` logic (only its `set_page_config` removal).

## 8. Execution log

| Date | Executor | Result |
|---|---|---|
| 2026-07-09 | Claude Opus 4.8 | **Implemented in full; all criteria met.** Part C: stripped `st.set_page_config` from all 12 pages (each a single line; grep-verified none remain, only `Home.py` has it). Part B: `pages/00_Home.py` = former Home body minus set_page_config + the Quick-Navigation card grid, plus an operator fleet-at-a-glance strip (online/weak-signal/segments-24h + link to Fleet Health). Part A: `Home.py` = thin `st.navigation` controller with the 4 sections exactly per §2. Commits `55c3ccc` (nav) + `<fix commit>` (bug fixes). **Verification found and fixed TWO real crashes that HTTP-200/curl hid** — this is the headline lesson: (1) `pages/12_Fleet_Health.py` threw `cannot convert float NaN to integer` in `_humanize_seconds` whenever an offline node (NaN uptime) existed — a latent bug from the Fleet Health work whose earlier "run the data pipeline" check never exercised the `st.metric` render path. Fixed (NaN→None). (2) An apparent "Multiple Pages/URL pathname Home" error surfaced ONLY when running the nav ENTRY (`Home.py`) through Streamlit `AppTest` — this is an AppTest artifact (AppTest runs single *pages*; the entry is a nav controller, and AppTest injects it as a phantom page). **Verification method that worked:** ran every leaf page through `AppTest.from_file(...).run()` inside the container (executes real page code, catches exceptions — all 13 clean), then for the entry, opened a genuine Streamlit session via a tornado websocket to `/_stcore/stream` (Streamlit auto-runs the script on connect) and scanned `docker logs` — **zero nav errors in the real app**. Do NOT trust `curl <page-url>` (identical SPA shell for every path) nor a data-pipeline-only check (misses the render path). Removed a no-op `url_path` I'd briefly added chasing the phantom (default pages always resolve to `""`). **Deviation:** touched `pages/12_Fleet_Health.py` beyond set_page_config removal — necessary because acceptance criterion #5 (every page renders without traceback) failed on its pre-existing NaN crash; it's a genuine correctness fix, minimal, logic otherwise untouched. Fleet/Wellbeing section order left as the approved mock (Wellbeing first) with the operator strip on Home; one-line swap documented in `Home.py` if Fleet-first is wanted later.|
