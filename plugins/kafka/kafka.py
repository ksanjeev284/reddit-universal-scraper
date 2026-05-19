"""
Kafka Streaming Plugin
Streams Reddit posts and comments to Kafka topics in JSON format.
"""
import sys
import os
import json
from pathlib import Path
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from plugins import Plugin

try:
    from confluent_kafka import Producer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("⚠️  confluent-kafka not installed. Run: pip install confluent-kafka")


class KafkaStreamer(Plugin):
    """Stream posts and comments to Kafka topics."""

    name = "kafka_streamer"
    description = "Streams posts and comments to Kafka in JSON format"
    enabled = True

    def __init__(self):
        super().__init__()
        self.producer: Optional[Producer] = None
        self._initialize_producer()

    def _initialize_producer(self):
        """Initialize Kafka producer from config file."""
        if not KAFKA_AVAILABLE:
            print(f"⚠️  Kafka plugin disabled: confluent-kafka not installed")
            self.enabled = False
            return

        # Get config file path from environment variable
        config_path = os.getenv('KAFKA_CONFIG_PATH')
        if not config_path:
            print(f"⚠️  KAFKA_CONFIG_PATH environment variable not set")
            self.enabled = False
            return

        config_file = Path(config_path)
        if not config_file.exists():
            print(f"⚠️  Kafka config file not found: {config_path}")
            self.enabled = False
            return

        # Load Kafka configuration from properties file
        try:
            kafka_config = self._load_config(config_file)

            # Get topic names from config or use defaults
            self.posts_topic = kafka_config.get('posts.topic', 'reddit-posts')
            self.comments_topic = kafka_config.get('comments.topic', 'reddit-comments')

            # Delete the conf before creating the producer
            kafka_config.__delitem__('posts.topic')
            kafka_config.__delitem__('comments.topic')
            self.producer = Producer(kafka_config)

            print(f"✅ Kafka producer initialized")
            print(f"   Posts topic: {self.posts_topic}")
            print(f"   Comments topic: {self.comments_topic}")

        except Exception as e:
            print(f"⚠️  Failed to initialize Kafka producer: {e}")
            self.enabled = False

    def _load_config(self, config_file: Path) -> dict:
        """Load configuration from properties file."""
        config = {}
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

        return config

    def _delivery_callback(self, err, msg):
        """Callback for message delivery reports."""
        if err:
            print(f"⚠️  Message delivery failed: {err}")
        # Uncomment for verbose delivery confirmation
        # else:
        #     print(f"✅ Message delivered to {msg.topic()} [{msg.partition()}]")

    def _send_to_kafka(self, topic: str, key: str, value: dict):
        """Send a message to Kafka."""
        if not self.producer:
            return

        try:
            # Serialize value to JSON
            json_value = json.dumps(value, ensure_ascii=False, default=str)

            # Produce message
            self.producer.produce(
                topic=topic,
                key=key.encode('utf-8') if key else None,
                value=json_value.encode('utf-8'),
                callback=self._delivery_callback
            )

            # Poll to handle delivery callbacks
            self.producer.poll(0)

        except Exception as e:
            print(f"⚠️  Failed to send message to Kafka: {e}")

    def process_posts(self, posts: list) -> list:
        """Stream posts to Kafka."""
        if not self.producer or not posts:
            return posts

        sent_count = 0
        for post in posts:
            # Use post ID as message key for partitioning
            key = post.get('id', '')
            self._send_to_kafka(self.posts_topic, key, post)
            sent_count += 1

        # Flush to ensure all messages are sent
        self.producer.flush()

        print(f"   📤 Streamed {sent_count} posts to Kafka topic '{self.posts_topic}'")
        return posts

    def process_comments(self, comments: list) -> list:
        """Stream comments to Kafka."""
        if not self.producer or not comments:
            return comments

        sent_count = 0
        for comment in comments:
            # Use parent ID = post Id as message key for partitioning
            key = comment.get('comment_id', '')
            self._send_to_kafka(self.comments_topic, key, comment)
            sent_count += 1

        # Flush to ensure all messages are sent
        self.producer.flush()

        print(f"   📤 Streamed {sent_count} comments to Kafka topic '{self.comments_topic}'")
        return comments

    def __del__(self):
        """Clean up producer on deletion."""
        if self.producer:
            # Flush any remaining messages
            self.producer.flush()
