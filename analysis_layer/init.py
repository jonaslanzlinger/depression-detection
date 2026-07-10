from fastapi import FastAPI

# Inbound adapters (routers)
from adapters.inbound.RestAnalyzeMetricsAdapter import create_service_analyze_metrics
from adapters.inbound.RestDeriveIndicatorScoresAdapter import (
    create_service_derive_indicator_scores,
)
from adapters.inbound.RestFinetuneBaselineAdapter import (
    create_service_finetune_baseline,
)
from adapters.inbound.RestListUsersAdapter import router as users_router
from adapters.inbound.RestBoardsAdapter import create_service_boards
from adapters.inbound.RestEnvironmentsAdapter import create_service_environments
from adapters.inbound.RestCalibrationAdapter import create_service_calibration
from adapters.inbound.RestComputeBaselineAdapter import create_service_compute_baseline

# Outbound adapters
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter

# Core
from core.use_cases.AnalyzeMetricsUseCase import AnalyzeMetricsUseCase
from core.use_cases.DeriveIndicatorScoresUseCase import DeriveIndicatorScoresUseCase
from core.baseline.BaselineManager import BaselineManager
from core.services.CalibrationService import CalibrationService
from core.mapping.ConfigManager import ConfigManager


# ---------------------------------------------------------
# Create FastAPI application
# ---------------------------------------------------------

app = FastAPI()

# ---------------------------------------------------------
# Instantiate core components
# ---------------------------------------------------------

# Create a shared ConfigManager instance
config_manager = ConfigManager()

# BaselineManager internally creates ConfigManager, but it's better if we could share it.
# However, modifying BaselineManager might be out of scope or risky if it relies on internal state.
# For now, we just pass our shared config_manager to DeriveIndicatorScoresUseCase.
# (Note: BaselineManager creates its own ConfigManager in __init__)
baseline_manager = BaselineManager()

repository = MongoPersistenceAdapter()
calibration_service = CalibrationService()

analyze_metrics_use_case = AnalyzeMetricsUseCase(repository)
derive_indicator_scores_use_case = DeriveIndicatorScoresUseCase(repository, config_manager)

# ---------------------------------------------------------
# Create routers from adapters
# ---------------------------------------------------------

app_analyze_metrics = create_service_analyze_metrics(
    analyze_metrics_use_case, baseline_manager
)
app_derive_indicator_scores = create_service_derive_indicator_scores(
    derive_indicator_scores_use_case
)
app_finetune_baseline = create_service_finetune_baseline(baseline_manager)
app_calibration = create_service_calibration(calibration_service)
app_compute_baseline = create_service_compute_baseline(baseline_manager)
app_boards = create_service_boards(repository)
app_environments = create_service_environments(repository)

# ---------------------------------------------------------
# Register routers with FastAPI
# ---------------------------------------------------------

app.include_router(app_analyze_metrics)
app.include_router(app_derive_indicator_scores)
app.include_router(app_finetune_baseline)
app.include_router(app_calibration)
app.include_router(app_compute_baseline)
app.include_router(users_router)
app.include_router(app_boards)
app.include_router(app_environments)


# ---------------------------------------------------------
# Config Mode Endpoint (Phase 3)
# ---------------------------------------------------------

@app.get("/config/mode")
async def get_config_mode():
    """Return the current configuration mode and related info."""
    # Reload to pick up any changes from MongoDB
    config_manager.reload_config()
    return {
        "mode": config_manager.get_config_mode(),
        "available_modes": ["legacy", "dynamic"],
        "metrics_count": len(config_manager.get_metric_list()),
        "description": {
            "legacy": "Original static descriptor mappings (config.json)",
            "dynamic": "Phase 2 behavioral dynamics mappings (config_dynamic_dsm5.json)",
        },
    }


@app.post("/config/reload")
async def reload_config():
    """Force reload configuration from MongoDB."""
    new_mode = config_manager.reload_config()
    return {
        "status": "reloaded",
        "mode": new_mode,
        "metrics_count": len(config_manager.get_metric_list()),
    }
