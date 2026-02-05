# Mac Mini Setup Guide

Complete setup instructions for deploying the RAG Teams Bot on a fresh Mac Mini.

## Prerequisites

- Mac Mini (Apple Silicon or Intel)
- Internet connection
- Microsoft Azure account
- Cloudflare account (free tier works)

---

## Part 1: Mac Mini System Setup

### Step 1: Install Xcode Command Line Tools

Open Terminal and run:

```bash
xcode-select --install
```

Click "Install" in the popup window and wait for it to complete (may take 5-10 minutes).

### Step 2: Install Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts. When it finishes, it will tell you to run two commands. They usually look like this:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Verify Homebrew is installed:

```bash
brew --version
```

### Step 3: Install Required Software

```bash
brew install python git ollama cloudflared
```

This installs:
- **Python 3** - Programming language
- **Git** - Version control
- **Ollama** - Local LLM server
- **Cloudflared** - Cloudflare tunnel client

### Step 4: Start Ollama Service

```bash
brew services start ollama
```

Wait 10 seconds for the service to start, then verify:

```bash
ollama --version
```

### Step 5: Download AI Models

This will download approximately 10GB of model data. Ensure you have a stable internet connection.

```bash
# Download the LLM (8-9 GB)
ollama pull qwen2.5:14b

# Download the embedding model (300 MB)
ollama pull nomic-embed-text
```

Verify models are installed:

```bash
ollama list
```

You should see both `qwen2.5:14b` and `nomic-embed-text` in the list.

---

## Part 2: Project Setup

### Step 6: Clone the Repository

```bash
cd ~
git clone https://github.com/elyousfy/rag-teams-bot.git
cd rag-teams-bot
```

### Step 7: Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

Your terminal prompt should now show `(venv)` at the beginning.

### Step 8: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 9: Create Required Directories

```bash
mkdir -p logs
mkdir -p data/documents
mkdir -p data/chroma
```

### Step 10: Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Edit the file to look like this (leave Azure fields blank for now):

```
# Azure Bot Configuration (fill in after Azure setup)
AZURE_APP_ID=
AZURE_APP_SECRET=
AZURE_TENANT_ID=
ALLOWED_AD_GROUP_ID=

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Paths
DOCUMENTS_PATH=./data/documents
CHROMA_PATH=./data/chroma

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

Save and exit: Press `Ctrl+X`, then `Y`, then `Enter`.

---

## Part 3: Add Documents

### Step 11: Add Your Company Documents

Copy your company documents to the `data/documents/` folder:

```bash
# Example: Copy from a USB drive
cp /Volumes/USB_DRIVE/documents/* ~/rag-teams-bot/data/documents/

# Or copy from another location
cp /path/to/your/documents/* ~/rag-teams-bot/data/documents/
```

Supported file formats:
- PDF files (`.pdf`)
- Word documents (`.docx`)
- Excel spreadsheets (`.xlsx`)
- PowerPoint presentations (`.pptx`)
- Markdown files (`.md`)
- Text files (`.txt`)
- CSV files (`.csv`)
- JSON files (`.json`)

### Step 12: Run Document Ingestion

```bash
cd ~/rag-teams-bot
source venv/bin/activate
python scripts/ingest.py
```

This will:
1. Load all documents from `data/documents/`
2. Split them into chunks
3. Create embeddings using the AI model
4. Store them in ChromaDB

Wait for it to complete. You should see a summary showing how many documents and chunks were processed.

---

## Part 4: Test Locally

### Step 13: Start the Server

```bash
cd ~/rag-teams-bot
source venv/bin/activate
python -m app.main
```

You should see output like:
```
INFO: Starting RAG Teams Bot...
INFO: RAG engine initialized successfully
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 14: Test the RAG System

Open a **new Terminal tab** (Cmd+T) and run:

```bash
cd ~/rag-teams-bot
source venv/bin/activate
python scripts/test_rag.py --interactive
```

Try asking questions about your documents. Type `quit` to exit.

### Step 15: Test the API

In another terminal:

```bash
# Health check
curl http://localhost:8000/health

# Should return something like:
# {"status":"healthy","rag_ready":true,"queue_size":0,"is_processing":false}
```

---

## Part 5: Azure Bot Setup

### Step 16: Create Azure Bot Resource

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"**
3. Search for **"Azure Bot"**
4. Click **"Create"**

Fill in the form:
- **Bot handle**: `company-docs-bot` (or your preferred name)
- **Subscription**: Select your subscription
- **Resource group**: Create new or use existing
- **Pricing tier**: Free (F0) for testing, Standard for production
- **Microsoft App ID**: Select "Create new Microsoft App ID"

Click **"Review + create"**, then **"Create"**.

### Step 17: Get Bot Credentials

After the bot is created:

1. Go to the bot resource
2. Click **"Configuration"** in the left sidebar
3. Note the **Microsoft App ID** (copy this)
4. Click **"Manage Password"** next to Microsoft App ID
5. Click **"New client secret"**
6. Add a description (e.g., "RAG Bot Secret")
7. Choose expiration (24 months recommended)
8. Click **"Add"**
9. **IMPORTANT**: Copy the secret value immediately (you won't see it again!)

### Step 18: Get Tenant ID

1. In Azure Portal, go to **"Microsoft Entra ID"** (formerly Azure Active Directory)
2. Click **"Overview"**
3. Copy the **"Tenant ID"**

### Step 19: Update Environment Variables

On your Mac Mini, edit the `.env` file:

```bash
cd ~/rag-teams-bot
nano .env
```

Fill in the Azure values:

```
AZURE_APP_ID=your-app-id-from-step-17
AZURE_APP_SECRET=your-secret-from-step-17
AZURE_TENANT_ID=your-tenant-id-from-step-18
ALLOWED_AD_GROUP_ID=
```

Save and exit: `Ctrl+X`, `Y`, `Enter`.

### Step 20: Create Azure AD Group (Optional)

To restrict bot access to specific users:

1. In Azure Portal, go to **"Microsoft Entra ID"**
2. Click **"Groups"** in the left sidebar
3. Click **"New group"**
4. Group type: **Security**
5. Group name: `RAG Bot Users`
6. Add members who should have access
7. Click **"Create"**
8. Open the group and copy the **"Object ID"**
9. Add this to your `.env` file as `ALLOWED_AD_GROUP_ID`

If you skip this step, all authenticated users can use the bot.

---

## Part 6: Cloudflare Tunnel Setup

### Step 21: Start a Quick Tunnel (Testing)

For initial testing, use a quick tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

This will output a URL like:
```
https://random-words-here.trycloudflare.com
```

**Copy this URL** - you'll need it for the next step.

Note: This URL changes every time you restart the tunnel. For production, set up a named tunnel (see Step 24).

### Step 22: Configure Bot Messaging Endpoint

1. Go back to your Azure Bot resource
2. Click **"Configuration"**
3. In **"Messaging endpoint"**, enter:
   ```
   https://your-cloudflare-url.trycloudflare.com/api/messages
   ```
4. Click **"Apply"**

### Step 23: Enable Teams Channel

1. In your Azure Bot resource, click **"Channels"**
2. Click **"Microsoft Teams"**
3. Accept the terms of service
4. Click **"Apply"**

### Step 24: Set Up Named Tunnel (Production)

For production, create a permanent tunnel:

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create a named tunnel
cloudflared tunnel create rag-bot

# Create config file
mkdir -p ~/.cloudflared
nano ~/.cloudflared/config.yml
```

Add this content:

```yaml
tunnel: rag-bot
credentials-file: /Users/YOUR_USERNAME/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: ragbot.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

Replace:
- `YOUR_USERNAME` with your Mac username
- `TUNNEL_ID` with the ID shown when you created the tunnel
- `ragbot.yourdomain.com` with your actual domain

Then set up DNS:

```bash
cloudflared tunnel route dns rag-bot ragbot.yourdomain.com
```

---

## Part 7: Run as a Service

### Step 25: Create Launch Agent

Create the service file:

```bash
nano ~/Library/LaunchAgents/com.company.ragbot.plist
```

Add this content (replace `/Users/YOUR_USERNAME` with your actual path):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.company.ragbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/rag-teams-bot/venv/bin/python</string>
        <string>-m</string>
        <string>app.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/rag-teams-bot</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/rag-teams-bot/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/rag-teams-bot/logs/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Save and exit: `Ctrl+X`, `Y`, `Enter`.

### Step 26: Load the Service

```bash
launchctl load ~/Library/LaunchAgents/com.company.ragbot.plist
```

### Step 27: Create Cloudflare Tunnel Service (Production)

```bash
nano ~/Library/LaunchAgents/com.company.cloudflared.plist
```

Add:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.company.cloudflared</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>rag-bot</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/rag-teams-bot/logs/cloudflared.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/rag-teams-bot/logs/cloudflared-error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.company.cloudflared.plist
```

---

## Part 8: Test in Teams

### Step 28: Add Bot to Teams

1. Open Microsoft Teams
2. Click **"Apps"** in the left sidebar
3. Search for your bot name
4. Click **"Add"**
5. Start a chat with the bot
6. Ask a question about your company documents!

### Step 29: Verify Everything Works

Send these messages to the bot:
- `/help` - Should show help message
- `What is the remote work policy?` - Should answer based on your documents
- `/clear` - Should clear conversation history

---

## Troubleshooting

### Bot not responding

1. Check server is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check logs:
   ```bash
   tail -f ~/rag-teams-bot/logs/stdout.log
   ```

3. Verify Cloudflare tunnel is running:
   ```bash
   curl https://your-tunnel-url.trycloudflare.com/health
   ```

### Ollama not working

```bash
# Check service status
brew services list

# Restart Ollama
brew services restart ollama

# Test Ollama directly
curl http://localhost:11434/api/tags
```

### Re-ingest documents

```bash
cd ~/rag-teams-bot
source venv/bin/activate
python scripts/ingest.py --clear
```

### Restart services

```bash
# Restart RAG bot
launchctl unload ~/Library/LaunchAgents/com.company.ragbot.plist
launchctl load ~/Library/LaunchAgents/com.company.ragbot.plist

# Restart Cloudflare tunnel
launchctl unload ~/Library/LaunchAgents/com.company.cloudflared.plist
launchctl load ~/Library/LaunchAgents/com.company.cloudflared.plist
```

### View service logs

```bash
# RAG bot logs
tail -100 ~/rag-teams-bot/logs/stdout.log

# Error logs
tail -100 ~/rag-teams-bot/logs/stderr.log

# Cloudflare logs
tail -100 ~/rag-teams-bot/logs/cloudflared.log
```

---

## Maintenance

### Adding New Documents

1. Copy new documents to `data/documents/`
2. Re-run ingestion:
   ```bash
   cd ~/rag-teams-bot
   source venv/bin/activate
   python scripts/ingest.py --clear
   ```
3. Restart the service:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.company.ragbot.plist
   launchctl load ~/Library/LaunchAgents/com.company.ragbot.plist
   ```

### Updating the Bot

```bash
cd ~/rag-teams-bot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
launchctl unload ~/Library/LaunchAgents/com.company.ragbot.plist
launchctl load ~/Library/LaunchAgents/com.company.ragbot.plist
```

### Checking Disk Space

The models and vector database can take significant space:

```bash
# Check Ollama models size
du -sh ~/.ollama

# Check ChromaDB size
du -sh ~/rag-teams-bot/data/chroma
```

---

## Security Notes

- The `.env` file contains secrets - never commit it to git
- Restrict Azure AD group access to authorized users only
- Keep the Mac Mini on a secure network
- Regularly rotate the Azure App Secret
- Monitor logs for unauthorized access attempts

---

## Support

For issues with:
- **This bot**: Check the logs and GitHub issues
- **Ollama**: https://github.com/ollama/ollama
- **Azure Bot**: https://docs.microsoft.com/en-us/azure/bot-service/
- **Cloudflare Tunnel**: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
