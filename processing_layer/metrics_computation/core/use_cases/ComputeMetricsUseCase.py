class ComputeMetricsUseCase:
    def __init__(self, user_profiling, persistence, metrics_computation_service):
        self.user_profiling = user_profiling
        self.persistence = persistence
        self.metrics_computation_service = metrics_computation_service

    def execute(self, audio_bytes: bytes):
        user_id = self.user_profiling.recognize_user(audio_bytes)
        metrics = self.metrics_computation_service.compute(audio_bytes, user_id)
        self.persistence.save_metrics(metrics)
