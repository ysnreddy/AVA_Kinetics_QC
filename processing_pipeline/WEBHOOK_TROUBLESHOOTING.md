# CVAT Webhook Connection Troubleshooting Guide

## 🚨 Current Issue
**Error**: "Last delivery was not successful, error 502"
**Configured URL**: `https://host.docker.internal:5001/webhook`

## 🔍 Root Cause Analysis

The **502 Bad Gateway** error occurs because:

1. **Protocol Mismatch**: CVAT is trying HTTPS but webhook_listener.py serves only HTTP
2. **Service Not Running**: webhook_listener.py might not be running
3. **Network Issue**: Docker container can't reach host machine

## ✅ Quick Fix Solutions

### Solution 1: Use HTTP Instead of HTTPS (Easiest)

1. In CVAT webhook configuration, change:
   - FROM: `https://host.docker.internal:5001/webhook`
   - TO: `http://host.docker.internal:5001/webhook`

2. Save and test the ping again

### Solution 2: Verify Webhook Listener is Running

1. Check if webhook_listener.py is running:
```bash
ps aux | grep webhook_listener
```

2. If not running, start it:
```bash
cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline
python webhook_listener.py
```

3. You should see:
```
✅ Service script detected at: /path/to/post_annotation_service.py
* Running on all addresses (0.0.0.0)
* Running on http://0.0.0.0:5001
```

## 🔧 Complete Setup Steps

### Step 1: Start the Webhook Listener

```bash
# Navigate to the processing pipeline directory
cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline

# Run the webhook listener
python webhook_listener.py
```

### Step 2: Test Connection Locally

```bash
# Test with curl
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{"event": "test", "message": "Hello webhook!"}'
```

### Step 3: Configure CVAT Webhook

1. Go to CVAT Admin → Your Project → Webhooks
2. Set Target URL to: `http://host.docker.internal:5001/webhook`
3. Select events to trigger on:
   - ✅ update:task
   - ✅ update:job
4. Save configuration
5. Click "Ping" to test

## 🔐 For HTTPS Support (Optional)

If you require HTTPS for security:

### 1. Generate SSL Certificates

```bash
cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline
chmod +x generate_certificates.sh
./generate_certificates.sh
```

### 2. Use HTTPS-Enabled Listener

```bash
# Use the HTTPS version instead
python webhook_listener_https.py
```

### 3. Configure CVAT for Self-Signed Certificates

In CVAT webhook settings, you may need to:
- Disable SSL verification (if option available)
- Or add certificate to CVAT's trusted store

## 🧪 Testing Tools

### Run Connection Diagnostic

```bash
cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/processing_pipeline
python test_webhook_connection.py
```

This will test multiple connection scenarios and tell you which one works.

## 📋 Checklist for Working Webhook

- [ ] webhook_listener.py is running
- [ ] Port 5001 is not blocked by firewall
- [ ] Using correct protocol (HTTP vs HTTPS)
- [ ] Correct hostname:
  - `host.docker.internal` (if CVAT in Docker)
  - `localhost` (if CVAT running locally)
  - Actual IP address of host machine
- [ ] CVAT webhook configuration saved
- [ ] Test ping shows success

## 🐳 Docker-Specific Configuration

If CVAT is running in Docker:

### Option 1: host.docker.internal (Recommended)
```
http://host.docker.internal:5001/webhook
```

### Option 2: Host Network Mode
Run webhook listener in Docker with host network:
```bash
docker run --network host -v $(pwd):/app python:3.9 python /app/webhook_listener.py
```

### Option 3: Use Host IP
Find your host machine IP:
```bash
# On Mac
ipconfig getifaddr en0

# On Linux
hostname -I
```
Then use: `http://YOUR_HOST_IP:5001/webhook`

## 🔍 Debugging Commands

### Check Port Availability
```bash
# Check if port 5001 is in use
lsof -i :5001

# Check if service is listening
netstat -an | grep 5001
```

### Monitor Webhook Logs
```bash
# In the terminal running webhook_listener.py, you'll see:
# - Incoming webhook requests
# - Success/failure messages
# - Task IDs being processed
```

### Test from Inside Docker
```bash
# If CVAT is in Docker, test from inside the container
docker exec -it cvat_container_name /bin/bash
curl http://host.docker.internal:5001/webhook
```

## ⚠️ Common Issues and Solutions

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Use HTTP instead of HTTPS |
| Connection Refused | Start webhook_listener.py |
| Timeout | Check firewall/network settings |
| 404 Not Found | Verify endpoint is `/webhook` |
| SSL Error | Use HTTP or setup proper certificates |

## 📝 Final Working Configuration

Based on your setup, the working configuration should be:

**CVAT Webhook Settings:**
- Target URL: `http://host.docker.internal:5001/webhook`
- Events: update:task, update:job
- Active: Yes

**webhook_listener.py running with:**
```python
app.run(host='0.0.0.0', port=5001, debug=True)
```

## Need More Help?

1. Check webhook_listener.py logs for detailed error messages
2. Use test_webhook_connection.py to diagnose connectivity
3. Verify post_annotation_service.py exists at the expected path
4. Ensure all Python dependencies are installed

---

*Last Updated: November 2024*