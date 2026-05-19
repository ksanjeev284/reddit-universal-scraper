# Kafka Streaming Plugin

This plugin streams Reddit posts and comments to Kafka topics in real-time using schemaless JSON format.

## Features

- ✅ Single Kafka Producer instance per session
- ✅ Configuration via properties file
- ✅ Schemaless JSON message format
- ✅ Separate topics for posts and comments
- ✅ Message key partitioning by post/comment ID
- ✅ Automatic message delivery confirmation
- ✅ Graceful error handling

## Installation

1. Install the Confluent Kafka Python client:
   ```bash
   pip install confluent-kafka
   ```

2. Create your Kafka configuration file:
   ```bash
   cp kafka.properties.example kafka.properties
   ```

3. Edit `kafka.properties` with your Kafka cluster settings:
   ```properties
   bootstrap.servers=your-kafka-broker:9092
   posts.topic=reddit-posts
   comments.topic=reddit-comments
   ```

## Configuration

### Environment Variable

Set the `KAFKA_CONFIG_PATH` environment variable to point to your configuration file:

```bash
export KAFKA_CONFIG_PATH=/path/to/kafka.properties
```

Or add it to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
echo 'export KAFKA_CONFIG_PATH=/path/to/kafka.properties' >> ~/.zshrc
```

### Configuration File Format

The plugin reads standard Kafka properties files with `key=value` format:

```properties
# Required settings
bootstrap.servers=localhost:9092

# Topic configuration
posts.topic=reddit-posts
comments.topic=reddit-comments

# Producer settings
acks=1
compression.type=snappy
linger.ms=10
batch.size=16384
```

## Message Format

### Posts Message
```json
{
  "id": "abc123",
  "title": "Post title",
  "selftext": "Post content",
  "author": "username",
  "subreddit": "subreddit_name",
  "score": 42,
  "created_utc": 1234567890,
  "url": "https://reddit.com/...",
  ...
}
```

### Comments Message
```json
{
  "id": "def456",
  "body": "Comment text",
  "author": "username",
  "score": 10,
  "created_utc": 1234567890,
  "parent_id": "t3_abc123",
  ...
}
```

## Usage

The plugin automatically activates when:
1. The `confluent-kafka` package is installed
2. The `KAFKA_CONFIG_PATH` environment variable is set
3. The configuration file exists and is valid

Simply run your scraper as normal:

```bash
python scraper.py
```

The plugin will stream posts and comments to Kafka automatically during scraping.

## Topic Partitioning

Messages are partitioned by their ID (post ID or comment ID) to ensure:
- Related messages go to the same partition
- Order is preserved for updates to the same post/comment
- Load is distributed across partitions

## Error Handling

The plugin includes graceful error handling:
- Missing configuration file → Plugin disabled
- Kafka connection issues → Error logged, scraping continues
- Message delivery failures → Logged with callback

## Monitoring

The plugin prints status messages:
- `✅ Kafka producer initialized` - Successful connection
- `📤 Streamed X posts to Kafka topic 'topic-name'` - Batch sent
- `⚠️ Message delivery failed: error` - Delivery issues

## Advanced Configuration

### Security (SSL/SASL)

For secure Kafka clusters, add to your `kafka.properties`:

```properties
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
sasl.username=your-username
sasl.password=your-password
ssl.ca.location=/path/to/ca-cert
```

### Performance Tuning

Adjust producer performance settings:

```properties
# Higher throughput
batch.size=32768
linger.ms=20
compression.type=lz4

# Lower latency
batch.size=0
linger.ms=0
acks=1
```

## Troubleshooting

### Plugin not loading
- Check if `confluent-kafka` is installed: `pip list | grep confluent`
- Verify `KAFKA_CONFIG_PATH` is set: `echo $KAFKA_CONFIG_PATH`
- Check configuration file exists: `ls -l $KAFKA_CONFIG_PATH`

### Connection issues
- Verify Kafka broker is accessible: `telnet your-broker 9092`
- Check `bootstrap.servers` in configuration
- Review Kafka broker logs

### No messages in topic
- Verify topics exist: `kafka-topics --list --bootstrap-server your-broker:9092`
- Check consumer group is reading from beginning
- Enable verbose delivery confirmation (uncomment in code)

## Disabling the Plugin

To temporarily disable the plugin:

1. Unset the environment variable:
   ```bash
   unset KAFKA_CONFIG_PATH
   ```

2. Or set `enabled = False` in the plugin class

3. Or uninstall confluent-kafka (not recommended)
