import os

def get_config_path():
    """
    Resolve the path to the analysis layer's indicator-mapping config.

    Honors the SAME config mode the analysis layer uses (legacy -> config.json,
    dynamic -> config_dynamic_dsm5.json) so the dashboard's feature/contribution views
    read the same metric set the scoring layer actually applies. Prioritizes the
    CONFIG_PATH env override, then searches common locations for the mode's file.
    """
    # 1. Explicit override
    if os.getenv("CONFIG_PATH"):
        return os.getenv("CONFIG_PATH")

    # 2. Pick the file for the active config mode (lazy import keeps this util light).
    try:
        from utils.database import get_config_mode
        mode = get_config_mode()
    except Exception:
        mode = os.getenv("CONFIG_MODE", "legacy").lower()
    filename = "config_dynamic_dsm5.json" if mode == "dynamic" else "config.json"

    # 3. Potential paths to check
    candidates = [
        # Relative from dashboard_layer (cwd) to analysis_layer
        f"../analysis_layer/core/mapping/{filename}",
        # Relative from repo root
        f"analysis_layer/core/mapping/{filename}",
        # Docker mount locations
        f"/app/analysis_layer/core/mapping/{filename}",
        f"/app/core/mapping/{filename}",
    ]

    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)

    # 4. Fallback
    return f"/app/core/mapping/{filename}"
