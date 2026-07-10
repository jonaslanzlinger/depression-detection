def get_jitter(features_LLD):
    """
    Compute jitter metric using openSMILE (eGeMAPS LLD)
    """
    if "jitterLocal_sma3nz" in features_LLD.columns:
        # sma3nz features are non-zero only for voiced frames
        jitter_voiced = features_LLD[features_LLD["jitterLocal_sma3nz"] > 0]["jitterLocal_sma3nz"]
        # NaN = "not measurable on this segment" (no voiced frames); the service
        # OMITS NaN metrics instead of persisting a fake 0.0 measurement.
        return jitter_voiced.mean() if not jitter_voiced.empty else float("nan")
    return float("nan")
