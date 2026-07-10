from ports.ConsumerPort import ConsumerPort
import queue
import threading
import time
import logging

logger = logging.getLogger(__name__)


class MqttConsumerAdapter(ConsumerPort):
    # Queue monitoring thresholds
    QUEUE_WARNING_THRESHOLD = 5
    QUEUE_CRITICAL_THRESHOLD = 10
    # Hard cap so a faster-than-realtime publisher can't grow the queue without bound and
    # OOM the (mem-limited) container. When full we drop the OLDEST queued message.
    QUEUE_MAX_DEPTH = 100

    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.topic_handlers = {}

        # Threaded processing with monitoring. Initialize ALL state the worker reads
        # BEFORE starting the thread -- otherwise the worker races __init__ and hits
        # AttributeError on _max_queue_depth/etc. on the first iterations.
        self.message_queue = queue.Queue(maxsize=self.QUEUE_MAX_DEPTH)
        self.is_running = True

        # Queue monitoring stats
        self._max_queue_depth = 0
        self._total_messages_processed = 0
        self._queue_warnings = 0

        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def register_handler(self, topic, handler: callable):
        if topic not in self.topic_handlers:
            self.topic_handlers[topic] = []
            self.client.subscribe(topic)
            print(f"Subscribed to topic: {topic}")
        self.topic_handlers[topic].append(handler)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        print("Connected to MQTT with result code", rc)
        for topic in self.topic_handlers:
            client.subscribe(topic)

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern with MQTT wildcards (# and +)."""
        if pattern == topic:
            return True

        # Handle # wildcard (matches any number of levels)
        if "#" in pattern:
            prefix = pattern.split("#")[0]
            return topic.startswith(prefix)

        # Handle + wildcard (matches single level)
        if "+" in pattern:
            pattern_parts = pattern.split("/")
            topic_parts = topic.split("/")
            if len(pattern_parts) != len(topic_parts):
                return False
            for p, t in zip(pattern_parts, topic_parts):
                if p != "+" and p != t:
                    return False
            return True

        return False

    def on_message(self, client, userdata, msg):
        # Offload processing to the worker thread immediately to keep the MQTT loop unblocked.
        # Bounded queue with drop-oldest: never block the network loop, never grow without
        # bound (a slow extractor + fast publisher would otherwise OOM the container).
        try:
            self.message_queue.put_nowait((msg.topic, msg.payload))
        except queue.Full:
            try:
                self.message_queue.get_nowait()  # drop oldest
                self.message_queue.task_done()
            except queue.Empty:
                pass
            try:
                self.message_queue.put_nowait((msg.topic, msg.payload))
            except queue.Full:
                logger.warning("message_queue full; dropping incoming message")

    def _worker(self):
        """Background thread to process messages from the queue with monitoring."""
        print("Worker thread started (with queue monitoring).")
        while self.is_running:
            try:
                # Monitor queue depth before processing
                queue_depth = self.message_queue.qsize()
                self._max_queue_depth = max(self._max_queue_depth, queue_depth)

                # Log warnings for queue backlog
                if queue_depth >= self.QUEUE_CRITICAL_THRESHOLD:
                    logger.error(
                        f"🚨 CRITICAL: MQTT queue backlog: {queue_depth} messages. "
                        f"Processing may be falling behind. Consider scaling."
                    )
                    self._queue_warnings += 1
                elif queue_depth >= self.QUEUE_WARNING_THRESHOLD:
                    logger.warning(
                        f"⚠️ WARNING: MQTT queue depth elevated: {queue_depth} messages. "
                        f"Monitor for sustained backlog."
                    )
                    self._queue_warnings += 1

                # Get message with timeout to allow checking is_running
                try:
                    topic, payload = self.message_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process message and track stats
                start_time = time.time()
                self._process_message(topic, payload)
                processing_time = time.time() - start_time

                self.message_queue.task_done()
                self._total_messages_processed += 1

                # Log slow processing (> 2 seconds)
                if processing_time > 2.0:
                    logger.warning(
                        f"⏱️ Slow message processing: {processing_time:.2f}s for topic {topic}"
                    )

                # Periodic stats (every 100 messages)
                if self._total_messages_processed % 100 == 0:
                    logger.info(
                        f"📊 MQTT Stats: {self._total_messages_processed} processed, "
                        f"max queue depth: {self._max_queue_depth}, warnings: {self._queue_warnings}"
                    )

            except Exception as e:
                logger.error(f"Error in worker thread: {e}")

    def get_queue_stats(self) -> dict:
        """Return current queue statistics for monitoring."""
        return {
            "current_depth": self.message_queue.qsize(),
            "max_depth": self._max_queue_depth,
            "total_processed": self._total_messages_processed,
            "warnings": self._queue_warnings,
        }

    def _process_message(self, topic, payload):
        """Actual message processing logic."""
        try:
            # Collect all matching handlers
            handlers = []

            # Try exact match first
            if topic in self.topic_handlers:
                handlers.extend(self.topic_handlers[topic])

            # Try wildcard matches
            for pattern, pattern_handlers in self.topic_handlers.items():
                if pattern != topic and self._topic_matches(pattern, topic):
                    handlers.extend(pattern_handlers)

            if not handlers:
                print(f"No handlers for topic: {topic}")
                return

            # Remove duplicates while preserving order
            seen = set()
            unique_handlers = []
            for h in handlers:
                if id(h) not in seen:
                    seen.add(id(h))
                    unique_handlers.append(h)

            for handler in unique_handlers:
                handler(topic, payload)
        except Exception as e:
            print("Error processing message:", e)

    def start(self):
        print("Starting MQTT adapter loop")
        self.client.loop_forever()
