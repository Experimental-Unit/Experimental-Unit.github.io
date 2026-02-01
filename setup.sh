#!/bin/bash
set -e

echo "=== OpenClaw 24/7 Setup ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Node.js version
check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${RED}Error: Node.js is not installed${NC}"
        echo "Install Node.js 22+: https://nodejs.org/"
        exit 1
    fi

    NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 22 ]; then
        echo -e "${RED}Error: Node.js 22+ required (found v$NODE_VERSION)${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Node.js v$(node -v | cut -d'v' -f2)"
}

# Install OpenClaw
install_openclaw() {
    echo ""
    echo "Installing OpenClaw..."

    if command -v pnpm &> /dev/null; then
        pnpm add -g openclaw@latest
    else
        npm install -g openclaw@latest
    fi

    echo -e "${GREEN}✓${NC} OpenClaw installed"
}

# Setup directories
setup_dirs() {
    echo ""
    echo "Setting up directories..."

    INSTALL_DIR="$HOME/openclaw"
    mkdir -p "$INSTALL_DIR/logs"
    mkdir -p "$INSTALL_DIR/data"
    mkdir -p "$INSTALL_DIR/workspace"

    # Copy config files
    cp openclaw.json "$INSTALL_DIR/"
    cp -r workspace/* "$INSTALL_DIR/workspace/"

    echo -e "${GREEN}✓${NC} Directories created at $INSTALL_DIR"
}

# Setup environment
setup_env() {
    echo ""
    INSTALL_DIR="$HOME/openclaw"

    if [ ! -f "$INSTALL_DIR/.env" ]; then
        echo "Setting up environment..."
        cp .env.example "$INSTALL_DIR/.env"
        echo -e "${YELLOW}!${NC} Edit $INSTALL_DIR/.env and add your ANTHROPIC_API_KEY"
    else
        echo -e "${GREEN}✓${NC} Environment file exists"
    fi
}

# Install systemd service
install_service() {
    echo ""
    echo "Installing systemd service..."

    # Create user service directory
    mkdir -p "$HOME/.config/systemd/user"

    # Copy and customize service file
    sed "s|%i|$USER|g" systemd/openclaw.service > "$HOME/.config/systemd/user/openclaw.service"
    sed -i "s|/home/$USER/openclaw|$HOME/openclaw|g" "$HOME/.config/systemd/user/openclaw.service"

    # Reload and enable
    systemctl --user daemon-reload
    systemctl --user enable openclaw.service

    echo -e "${GREEN}✓${NC} Systemd service installed"
}

# Start service
start_service() {
    echo ""
    read -p "Start OpenClaw now? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        systemctl --user start openclaw.service
        sleep 2

        if systemctl --user is-active --quiet openclaw.service; then
            echo -e "${GREEN}✓${NC} OpenClaw is running"
            echo ""
            echo "WebChat: http://127.0.0.1:18790"
            echo "Gateway: ws://127.0.0.1:18789"
        else
            echo -e "${RED}Failed to start. Check logs:${NC}"
            echo "journalctl --user -u openclaw.service -f"
        fi
    fi
}

# Enable linger for 24/7 operation
enable_linger() {
    echo ""
    echo "Enabling user linger for 24/7 operation..."

    if command -v loginctl &> /dev/null; then
        sudo loginctl enable-linger "$USER" 2>/dev/null || {
            echo -e "${YELLOW}!${NC} Could not enable linger (requires sudo)"
            echo "  Run manually: sudo loginctl enable-linger $USER"
        }
    fi
}

# Main
main() {
    check_node
    install_openclaw
    setup_dirs
    setup_env
    install_service
    enable_linger
    start_service

    echo ""
    echo "=== Setup Complete ==="
    echo ""
    echo "Commands:"
    echo "  Start:   systemctl --user start openclaw"
    echo "  Stop:    systemctl --user stop openclaw"
    echo "  Status:  systemctl --user status openclaw"
    echo "  Logs:    journalctl --user -u openclaw -f"
    echo "  Chat:    openclaw chat"
    echo ""
}

main
