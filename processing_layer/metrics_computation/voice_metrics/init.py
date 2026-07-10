import os
from paho.mqtt.client import Client, CallbackAPIVersion
from adapters.inbound.MqttConsumerAdapter import (
    MqttConsumerAdapter,
)
from adapters.outbound.RestUserProfilingAdapter import RestUserProfilingAdapter
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter
from adapters.outbound.NodeEnrollmentAdapter import NodeEnrollmentAdapter
from core.use_cases.ComputeMetricsUseCase import ComputeMetricsUseCase
from core.MetricsComputationService import MetricsComputationService
from adapters.inbound.handlers.ComputeMetricsHandler import ComputeMetricsHandler

client = Client(callback_api_version=CallbackAPIVersion.VERSION2)
# MQTT auth from env (no-op if MQTT_USER unset).
_mqtt_user = os.getenv("MQTT_USER")
if _mqtt_user:
    client.username_pw_set(_mqtt_user, os.getenv("MQTT_PASS"))

# wire all dependencies
user_profiling = RestUserProfilingAdapter()
persistence = MongoPersistenceAdapter()
metrics_computation_service = MetricsComputationService()
enrollment = NodeEnrollmentAdapter()

comput_metrics_use_case = ComputeMetricsUseCase(
    user_profiling, persistence, metrics_computation_service, enrollment=enrollment
)
mqtt_adapter = MqttConsumerAdapter(client)

# setup all handlers
compute_metrics_handler = ComputeMetricsHandler(comput_metrics_use_case)

# register the handlers at the MQTTAdapter
# Subscribe to wildcard topic for all boards: voice/{user_id}/{board_id}/{environment}
mqtt_adapter.register_handler("voice/#", compute_metrics_handler)
# Backward compatibility: also listen to legacy topic
mqtt_adapter.register_handler("voice/mic1", compute_metrics_handler)


client.connect(os.getenv("MQTT_HOST", "mqtt"), int(os.getenv("MQTT_PORT", "1883")), 60)
mqtt_adapter.start()
