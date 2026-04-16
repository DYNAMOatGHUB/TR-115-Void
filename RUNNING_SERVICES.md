# Running Producer & Consumer Services

There are multiple ways to run the producer and consumer services automatically without manual terminal commands.

## Method 1: Shell Script (Recommended for Development)

### Quick Start

```bash
# Start both services
./startup.sh start

# Check status
./startup.sh status

# View logs
./startup.sh logs

# Restart services
./startup.sh restart

# Stop services
./startup.sh stop
```

### What it does:
- ✓ Automatically loads `.env` variables
- ✓ Runs producer and consumer in background with `nohup`
- ✓ Logs output to `logs/producer.log` and `logs/consumer.log`
- ✓ Checks if services are already running
- ✓ Shows PID and log file locations

### One-time setup:
```bash
# Make sure the script is executable
chmod +x startup.sh
```

### View logs while running:
```bash
# In a new terminal
tail -f logs/producer.log logs/consumer.log
```

### Troubleshooting:
```bash
# Check if services are actually running
ps aux | grep python | grep -E "producer|consumer"

# Check logs for errors
cat logs/producer.log
cat logs/consumer.log

# Kill all services (if needed)
./startup.sh stop
```

---

## Method 2: Systemd Services (For Production / Always-On)

Systemd will automatically restart services if they crash, and start them on system boot.

### Installation

```bash
# Copy service files to systemd directory
sudo cp carbon-producer.service /etc/systemd/system/
sudo cp carbon-consumer.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable carbon-producer.service
sudo systemctl enable carbon-consumer.service
```

### Usage

```bash
# Start services
sudo systemctl start carbon-producer
sudo systemctl start carbon-consumer

# Check status
sudo systemctl status carbon-producer
sudo systemctl status carbon-consumer

# View logs (last 50 lines)
sudo journalctl -u carbon-producer -n 50
sudo journalctl -u carbon-consumer -n 50

# Stream logs in real-time
sudo journalctl -u carbon-producer -f
sudo journalctl -u carbon-consumer -f

# Restart services
sudo systemctl restart carbon-producer
sudo systemctl restart carbon-consumer

# Stop services
sudo systemctl stop carbon-producer
sudo systemctl stop carbon-consumer

# Disable auto-start on boot
sudo systemctl disable carbon-producer
sudo systemctl disable carbon-consumer
```

### Service Files Customize

If your username or project path is different, edit the service files:

```bash
# Replace ghostofsparta with your actual username
# Replace /home/ghostofsparta/cd_key_Projects/project with your actual path
sudo nano /etc/systemd/system/carbon-producer.service
sudo nano /etc/systemd/system/carbon-consumer.service

# Then reload
sudo systemctl daemon-reload
```

---

## Method 3: Manual with Screen (For Testing)

Create a screen session that persists when you disconnect:

```bash
# Start producer in background screen
screen -d -m -S carbon-producer python producer.py

# Start consumer in another screen
screen -d -m -S carbon-consumer python consumer.py

# List running screens
screen -ls

# Attach to producer screen
screen -r carbon-producer

# Detach from screen (Ctrl + A, then D)

# Kill a screen session
screen -S carbon-producer -X quit
```

---

## Method 4: Docker Compose (For Full Stack)

If you want to run everything (Kafka, producer, consumer, app) together:

The existing `docker-compose.yaml` runs Kafka infrastructure. You can extend it:

```bash
# Make sure Docker is running
docker-compose up -d

# View logs
docker-compose logs -f producer consumer

# Stop all services
docker-compose down
```

---

## Troubleshooting

### "Services not starting"
1. Check that `.env` file exists with correct variable names:
   ```bash
   cat .env | grep SMTP
   # Should show: SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD
   ```

2. Check dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. Verify Kafka/Redpanda is running:
   ```bash
   # Check if Redpanda is running (if using Docker)
   docker ps | grep redpanda
   ```

### "Email still not working"
- Verify .env variables are loaded:
  ```bash
  python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.environ.get('SENDER_EMAIL'))"
  ```
- Check Gmail app password format: `hyek mrgu awwg blwb` (16 chars, 4 groups)
- Enable 2FA on Gmail: https://myaccount.google.com/security

### "Consumer not processing events"
1. Check producer is running: `./startup.sh status`
2. Verify Kafka is accessible:
   ```bash
   nc -zv localhost 9092  # Should show "succeeded"
   ```
3. Check consumer logs: `tail -f logs/consumer.log`

### "Port already in use"
```bash
# Find what's using port 9092 (Kafka)
lsof -i :9092

# Kill the process
kill -9 <PID>
```

---

## Best Practices

✓ **Use shell script** for development and testing  
✓ **Use systemd** for production servers  
✓ **Always check logs** when services don't start  
✓ **Test email** after configuration before going live  
✓ **Monitor resource usage** if running 24/7  

## Summary

| Method | Best For | Difficulty | Auto-Restart | Logs |
|--------|----------|-----------|--------------|------|
| Shell Script | Development | ⭐ Easy | Manual | File-based |
| Systemd | Production | ⭐⭐ Medium | Yes | Journalctl |
| Screen | Testing | ⭐ Easy | No | Screen buffer |
| Docker | Full Stack | ⭐⭐ Medium | Yes | Docker logs |

---

## One-liner Quick Start

```bash
# Start everything right now
source .venv/bin/activate && ./startup.sh start && sleep 2 && python app.py
```

Then open http://localhost:7860 in your browser!
