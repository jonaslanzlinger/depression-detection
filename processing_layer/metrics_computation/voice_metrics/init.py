from paho.mqtt.client import Client, CallbackAPIVersion
from adapters.inbound.MqttAdapter import MqttAdapter
from adapters.outbound.RestUserProfilingAdapter import RestUserProfilingAdapter
from adapters.outbound.MongoPersistenceAdapter import MongoPersistenceAdapter
from core.use_cases.ComputeMetricsUseCase import ComputeMetricsUseCase
from core.MetricsComputationService import MetricsComputationService
from adapters.inbound.handlers.ComputeMetricsHandler import ComputeMetricsHandler

client = Client(callback_api_version=CallbackAPIVersion.VERSION2)

# wire all dependencies
user_profiling = RestUserProfilingAdapter()
persistence = MongoPersistenceAdapter()
metrics_computation_service = MetricsComputationService()

comput_metrics_use_case = ComputeMetricsUseCase(
    user_profiling, persistence, metrics_computation_service
)
mqtt_adapter = MqttAdapter(client)

# setup all handlers
compute_metrics_handler = ComputeMetricsHandler(comput_metrics_use_case)

# register the handlers at the MQTTAdapter
mqtt_adapter.register_handler("voice/mic1", compute_metrics_handler)

client.on_connect = mqtt_adapter.on_connect
client.on_message = mqtt_adapter.on_message

client.connect("mqtt", 1883, 60)
client.loop_forever()
