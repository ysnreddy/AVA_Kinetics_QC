# CVAT Webhook Issues - Resolution Documentation

## Overview
This document explains how we resolved two critical webhook issues that prevented CVAT from communicating with our webhook listener service.

---

## Issue 1: 502 Bad Gateway Error

### Problem Description
- **Error**: "Last delivery was not successful, error 502"
- **Webhook URL**: `https://host.docker.internal:5001/webhook` (using HTTPS)
- **Root Cause**: Protocol mismatch - CVAT was trying to connect via HTTPS, but the webhook listener was running on HTTP

### Investigation Process
1. Checked the webhook_listener.py configuration:
   ```python
   app.run(host='0.0.0.0', port=5001, debug=True)
   ```
   This runs a standard Flask server on HTTP, not HTTPS

2. Realized Flask wasn't configured for SSL/TLS

### Resolution
**Changed the webhook URL from HTTPS to HTTP**

- **Where**: CVAT Webhook Settings (UI)
- **What Changed**:
  - FROM: `https://host.docker.internal:5001/webhook`
  - TO: `http://host.docker.internal:5001/webhook`
- **Why**: The Flask webhook listener runs on HTTP by default without SSL configuration

### Alternative Solutions (Not Implemented)
1. Could have added SSL to Flask:
   ```python
   app.run(host='0.0.0.0', port=5001, ssl_context='adhoc')
   ```
2. Could have used a reverse proxy (nginx) with SSL termination

---

## Issue 2: 407 Proxy Authentication Required

### Problem Description
- **Error**: "407 Proxy Authentication Required"
- **Error Details**: "The destination address (192.168.65.254) was denied by rule 'Deny: Private Range'"
- **Root Cause**: Smokescreen (CVAT's security proxy) was blocking connections to private IP ranges

### Investigation Process
1. Initially thought it was a corporate proxy issue
2. Created docker-compose.override.yml to unset proxy variables
3. Discovered the real cause: **Smokescreen proxy** blocking private IPs
   - Smokescreen is CVAT's built-in SSRF protection
   - It blocks requests to private IP ranges by default
   - `host.docker.internal` resolves to private IP (192.168.65.254)

### Resolution
**Configured Smokescreen to allow private IP ranges**

#### Files Modified:

1. **`/Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/cvat/docker-compose.override.yml`**
   ```yaml
   version: '3.3'
   services:
     cvat_server:
       environment:
         # Unset empty proxy variables
         - http_proxy
         - https_proxy
         - HTTP_PROXY
         - HTTPS_PROXY
         # Set no_proxy for local connections
         - no_proxy=localhost,127.0.0.1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
         - NO_PROXY=localhost,127.0.0.1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
         # Allow Smokescreen to connect to private IP ranges
         - SMOKESCREEN_OPTS=--allow-range 192.168.0.0/16 --allow-range 172.16.0.0/12 --allow-range 10.0.0.0/8

     cvat_worker_webhooks:
       environment:
         # Same configuration as cvat_server
         - http_proxy
         - https_proxy
         - HTTP_PROXY
         - HTTPS_PROXY
         - no_proxy=localhost,127.0.0.1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
         - NO_PROXY=localhost,127.0.0.1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
         - SMOKESCREEN_OPTS=--allow-range 192.168.0.0/16 --allow-range 172.16.0.0/12 --allow-range 10.0.0.0/8
   ```

2. **`/Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/cvat/.env`**
   ```bash
   # Explicitly unset proxy variables to avoid 407 errors
   http_proxy=
   https_proxy=
   HTTP_PROXY=
   HTTPS_PROXY=

   # No proxy list
   no_proxy=localhost,127.0.0.1,host.docker.internal,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
   ```

#### What These Changes Do:
- **Unset empty proxy variables**: Prevents Docker from passing empty proxy settings that cause 407 errors
- **Configure no_proxy**: Ensures local connections bypass any proxy
- **SMOKESCREEN_OPTS**: Allows Smokescreen to connect to private IP ranges:
  - `192.168.0.0/16`: Private network range
  - `172.16.0.0/12`: Docker internal networks
  - `10.0.0.0/8`: Private network range

#### Applied Changes:
```bash
cd /Users/Surya/AVA_Kinetics/AVA_Kinetics_QC/cvat
docker-compose down
docker-compose up -d
```

---

## Summary

### Issue 1 (502 Error) - Protocol Mismatch
- **Fix Location**: CVAT UI Webhook Settings
- **Fix**: Changed URL from `https://` to `http://`
- **Reason**: Flask webhook listener runs on HTTP, not HTTPS

### Issue 2 (407 Error) - Smokescreen Blocking
- **Fix Location**: Docker configuration files
- **Files Created/Modified**:
  - `cvat/docker-compose.override.yml` - Added Smokescreen configuration
  - `cvat/.env` - Unset empty proxy variables
- **Fix**: Allowed private IP ranges in Smokescreen
- **Reason**: Smokescreen was blocking connections to private IPs for security

### Key Learnings
1. **502 errors** often indicate protocol mismatches or service unavailability
2. **407 errors** can come from multiple sources:
   - Corporate proxies (not the case here)
   - Security proxies like Smokescreen (the actual cause)
3. **Smokescreen** is CVAT's SSRF protection that needs configuration for local development
4. **Docker containers** need restart to pick up new environment configurations

---

## Testing the Fix
1. Direct connection test:
   ```bash
   docker exec cvat_worker_webhooks curl -X POST http://host.docker.internal:5001/webhook
   ```
   Result: 200 OK

2. Through Smokescreen proxy:
   ```bash
   docker exec cvat_worker_webhooks curl -x http://localhost:4750 -X POST http://host.docker.internal:5001/webhook
   ```
   Result: 200 OK

3. CVAT UI: Webhook "Ping" button now works successfully