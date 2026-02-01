# OpenClaw 24/7 Setup

A minimal [OpenClaw](https://openclaw.ai) configuration for running your AI assistant 24/7.

## Quick Start

```bash
# Clone and run setup
git clone https://github.com/Experimental-Unit/Experimental-Unit.github.io.git openclaw
cd openclaw
chmod +x setup.sh
./setup.sh
```

## Requirements

- Node.js 22+
- systemd (Linux)
- Anthropic API key

## Manual Installation

```bash
# Install OpenClaw
npm install -g openclaw@latest

# Copy config to home directory
mkdir -p ~/openclaw/logs ~/openclaw/data ~/openclaw/workspace
cp openclaw.json ~/openclaw/
cp workspace/* ~/openclaw/workspace/
cp .env.example ~/openclaw/.env

# Edit your API key
nano ~/openclaw/.env

# Run onboarding
openclaw onboard --install-daemon
```

## Configuration

Edit `openclaw.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `agent.model` | claude-sonnet-4-20250514 | Primary LLM |
| `gateway.port` | 18789 | WebSocket port |
| `channels.webchat.port` | 18790 | Web UI port |
| `daemon.autoRestart` | true | Restart on crash |

## Running 24/7

### With systemd (Recommended)

```bash
# Install service
cp systemd/openclaw.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable openclaw
systemctl --user start openclaw

# Enable linger (keeps running after logout)
sudo loginctl enable-linger $USER
```

### Commands

```bash
systemctl --user start openclaw    # Start
systemctl --user stop openclaw     # Stop
systemctl --user restart openclaw  # Restart
systemctl --user status openclaw   # Status
journalctl --user -u openclaw -f   # Logs
```

### With Docker

```bash
docker run -d \
  --name openclaw \
  --restart always \
  -p 18789:18789 \
  -p 18790:18790 \
  -v ~/openclaw:/app/config \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  openclaw/openclaw:latest
```

## Usage

### Web Interface

Open http://127.0.0.1:18790

### CLI

```bash
openclaw chat
```

### API

```bash
# WebSocket
wscat -c ws://127.0.0.1:18789
```

## Files

```
.
├── openclaw.json      # Main configuration
├── workspace/
│   └── AGENTS.md      # Agent personality
├── systemd/
│   └── openclaw.service
├── setup.sh           # Automated setup
└── .env.example       # Environment template
```

## Troubleshooting

**Service won't start:**
```bash
journalctl --user -u openclaw -n 50
```

**Port already in use:**
```bash
lsof -i :18789
```

**Check if running:**
```bash
curl http://127.0.0.1:18790/health
```

## Links

- [OpenClaw Docs](https://docs.openclaw.ai)
- [OpenClaw GitHub](https://github.com/openclaw/openclaw)
- [Discord](https://discord.gg/clawd)
