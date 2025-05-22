class MqttAdapter:
    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.topic_handlers = {}

    def register_handler(self, topic, handler):
        if topic not in self.topic_handlers:
            self.topic_handlers[topic] = []
            self.client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")
        self.topic_handlers[topic].append(handler)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("Connected to MQTT with result code", rc)
        for topic in self.topic_handlers:
            client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        try:
            handlers = self.topic_handlers.get(msg.topic, [])
            if not handlers:
                print(f"No handlers for topic: {msg.topic}")
                return
            for handler in handlers:
                handler(msg.topic, msg.payload)
        except Exception as e:
            print("Error processing message:", e)
