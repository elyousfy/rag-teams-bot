# RAG Teams Bot for Company Docs

A self-hosted RAG system that lets department members ask questions about company documents via Microsoft Teams.

## Architecture

```
Microsoft Teams → Cloudflare Tunnel → FastAPI → LlamaIndex → ChromaDB
                                                     ↓
                                              Ollama (qwen2.5:14b)
```

All components run locally. No data leaves your network except chat messages through Teams.

## Requirements

- Python 3.10+
- Ollama with `qwen2.5:14b` and `nomic-embed-text` models
- Microsoft Azure account (for Teams bot registration)
- Cloudflare account (for tunnel)

## Quick Start

### 1. Install Ollama Models

```bash
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### 2. Install Python Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Add Documents

Place your documents in `data/documents/`:
- PDF files
- Word documents (.docx)
- Excel spreadsheets (.xlsx)
- PowerPoint presentations (.pptx)
- Markdown files (.md)
- Text files (.txt)

### 5. Run Document Ingestion

```bash
python scripts/ingest.py
```

### 6. Start the Server

```bash
python -m app.main
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7. Test Locally

```bash
# Health check
curl http://localhost:8000/health

# Test query (requires documents to be ingested)
curl -X POST http://localhost:8000/api/test \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the company policy on remote work?", "user_id": "test"}'
```

## Azure Bot Setup

### 1. Register Bot in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Create a new "Azure Bot" resource
3. Note the **App ID** (Microsoft App ID)
4. Note your **Tenant ID** (found in Azure AD > Properties)
5. Create a new client secret and note the **App Secret**

### 2. Configure Messaging Endpoint

After setting up Cloudflare Tunnel (see below), configure the messaging endpoint:

```
https://your-tunnel-domain.trycloudflare.com/api/messages
```

### 3. Enable Teams Channel

In the Azure Bot resource:
1. Go to Channels
2. Add Microsoft Teams channel
3. Accept the terms of service

### 4. Create Azure AD Group (Optional)

To restrict access:
1. Create a Security Group in Azure AD
2. Add authorized users
3. Copy the Group Object ID to `ALLOWED_AD_GROUP_ID` in `.env`

## Cloudflare Tunnel Setup

### 1. Install cloudflared

```bash
# macOS
brew install cloudflare/cloudflare/cloudflared

# Or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

### 2. Quick Tunnel (Development)

```bash
cloudflared tunnel --url http://localhost:8000
```

### 3. Named Tunnel (Production)

```bash
# Login
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create rag-bot

# Configure tunnel (create config.yml)
# Run tunnel
cloudflared tunnel run rag-bot
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AZURE_APP_ID` | Bot's Microsoft App ID | Required |
| `AZURE_APP_SECRET` | Bot's client secret | Required |
| `AZURE_TENANT_ID` | Azure AD tenant ID | Required |
| `ALLOWED_AD_GROUP_ID` | Azure AD group for access control | Optional |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_LLM_MODEL` | LLM model name | `qwen2.5:14b` |
| `OLLAMA_EMBED_MODEL` | Embedding model name | `nomic-embed-text` |
| `DOCUMENTS_PATH` | Path to documents folder | `./data/documents` |
| `CHROMA_PATH` | Path to ChromaDB storage | `./data/chroma` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |

### RAG Configuration

Edit `app/config.py` to adjust:
- `CHUNK_SIZE`: Token size for document chunks (default: 512)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 50)
- `TOP_K`: Number of chunks retrieved (default: 5)
- `CONVERSATION_MEMORY_SIZE`: Messages to remember (default: 5)

## Bot Commands

- `/help` - Show help message
- `/clear` - Clear conversation history

## Production Deployment (macOS launchd)

Create `~/Library/LaunchAgents/com.company.ragbot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.company.ragbot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>-m</string>
        <string>app.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/rag-teams-bot</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/rag-teams-bot/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/rag-teams-bot/logs/stderr.log</string>
</dict>
</plist>
```

Load the service:

```bash
launchctl load ~/Library/LaunchAgents/com.company.ragbot.plist
```

## Troubleshooting

### No documents found

Ensure documents are in `data/documents/` and run:
```bash
python scripts/ingest.py --clear
```

### Ollama connection error

Check Ollama is running:
```bash
ollama list
curl http://localhost:11434/api/tags
```

### Bot not responding in Teams

1. Check the Cloudflare tunnel is running
2. Verify the messaging endpoint in Azure Portal
3. Check application logs in `logs/`

### Unauthorized error

Ensure your Azure AD user is in the configured group, or remove `ALLOWED_AD_GROUP_ID` to allow all authenticated users.

## File Structure

```
rag-teams-bot/
├── app/
│   ├── main.py           # FastAPI entry point
│   ├── bot_handler.py    # Teams webhook handling
│   ├── auth.py           # Azure AD group validation
│   ├── rag_engine.py     # LlamaIndex query logic
│   ├── queue_worker.py   # Async request processing
│   └── config.py         # Settings from .env
├── scripts/
│   └── ingest.py         # Document ingestion CLI
├── data/
│   ├── documents/        # Source docs (gitignored)
│   └── chroma/           # Vector DB (gitignored)
├── logs/                 # Application logs
├── .env.example          # Template for secrets
├── .env                  # Actual secrets (gitignored)
├── requirements.txt
└── README.md
```

## License

Internal use only.
