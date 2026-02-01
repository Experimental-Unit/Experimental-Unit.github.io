#!/bin/bash
# OpenClaw Local Setup Script
# This script installs and configures OpenClaw for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  OpenClaw Local Setup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Check for required dependencies
check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"

    # Check Node.js version
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VERSION" -ge 22 ]; then
            echo -e "${GREEN}✓ Node.js v$(node -v) found${NC}"
        else
            echo -e "${RED}✗ Node.js 22+ required (found v$(node -v))${NC}"
            echo -e "  Install with: nvm install 22"
            exit 1
        fi
    else
        echo -e "${RED}✗ Node.js not found${NC}"
        echo -e "  Install from: https://nodejs.org/"
        exit 1
    fi

    # Check for pnpm (preferred) or npm
    if command -v pnpm &> /dev/null; then
        echo -e "${GREEN}✓ pnpm $(pnpm -v) found${NC}"
        PKG_MANAGER="pnpm"
    elif command -v npm &> /dev/null; then
        echo -e "${YELLOW}○ npm found (pnpm recommended for better performance)${NC}"
        PKG_MANAGER="npm"
    else
        echo -e "${RED}✗ No package manager found${NC}"
        exit 1
    fi

    # Check for git
    if command -v git &> /dev/null; then
        echo -e "${GREEN}✓ git $(git --version | cut -d' ' -f3) found${NC}"
    else
        echo -e "${RED}✗ git not found${NC}"
        exit 1
    fi

    # Check for Docker (optional but recommended)
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✓ Docker found (sandbox mode available)${NC}"
        DOCKER_AVAILABLE=true
    else
        echo -e "${YELLOW}○ Docker not found (sandbox mode disabled)${NC}"
        DOCKER_AVAILABLE=false
    fi

    # Check for Python (for pipeline)
    if command -v python3 &> /dev/null; then
        echo -e "${GREEN}✓ Python $(python3 --version | cut -d' ' -f2) found${NC}"
    else
        echo -e "${YELLOW}○ Python not found (required for pipeline)${NC}"
    fi

    echo
}

# Install OpenClaw globally
install_openclaw() {
    echo -e "${YELLOW}Installing OpenClaw...${NC}"

    if [ "$PKG_MANAGER" = "pnpm" ]; then
        pnpm add -g openclaw@latest
    else
        npm install -g openclaw@latest
    fi

    if command -v openclaw &> /dev/null; then
        echo -e "${GREEN}✓ OpenClaw installed successfully${NC}"
        openclaw --version
    else
        echo -e "${RED}✗ OpenClaw installation failed${NC}"
        exit 1
    fi

    echo
}

# Configure OpenClaw for this project
configure_openclaw() {
    echo -e "${YELLOW}Configuring OpenClaw for this project...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    OPENCLAW_DIR="$PROJECT_ROOT/openclaw"

    # Create symlink to project config in user's home
    OPENCLAW_HOME="$HOME/.openclaw"
    mkdir -p "$OPENCLAW_HOME"

    # Backup existing config if present
    if [ -f "$OPENCLAW_HOME/openclaw.json" ]; then
        echo -e "${YELLOW}Backing up existing config...${NC}"
        mv "$OPENCLAW_HOME/openclaw.json" "$OPENCLAW_HOME/openclaw.json.backup.$(date +%Y%m%d%H%M%S)"
    fi

    # Create symlink to project config
    ln -sf "$OPENCLAW_DIR/openclaw.json" "$OPENCLAW_HOME/openclaw.json"
    echo -e "${GREEN}✓ Configuration linked${NC}"

    # Create symlink to workspace
    if [ -d "$OPENCLAW_HOME/workspace" ]; then
        mv "$OPENCLAW_HOME/workspace" "$OPENCLAW_HOME/workspace.backup.$(date +%Y%m%d%H%M%S)"
    fi
    ln -sf "$OPENCLAW_DIR/workspace" "$OPENCLAW_HOME/workspace"
    echo -e "${GREEN}✓ Workspace linked${NC}"

    # Create logs directory
    mkdir -p "$OPENCLAW_DIR/logs"
    echo -e "${GREEN}✓ Logs directory created${NC}"

    # Update sandbox config if Docker not available
    if [ "$DOCKER_AVAILABLE" = false ]; then
        echo -e "${YELLOW}Disabling Docker sandbox (Docker not available)...${NC}"
        # Use sed to update the config - disable sandbox
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' 's/"mode": "docker"/"mode": "none"/' "$OPENCLAW_DIR/openclaw.json"
        else
            sed -i 's/"mode": "docker"/"mode": "none"/' "$OPENCLAW_DIR/openclaw.json"
        fi
    fi

    echo
}

# Setup environment variables
setup_environment() {
    echo -e "${YELLOW}Setting up environment...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    # Check for .env file
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            echo -e "${YELLOW}Creating .env from .env.example...${NC}"
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
            echo -e "${YELLOW}⚠ Please edit .env and add your API keys${NC}"
        fi
    else
        echo -e "${GREEN}✓ .env file exists${NC}"
    fi

    # Check for Anthropic API key
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        echo -e "${GREEN}✓ ANTHROPIC_API_KEY is set${NC}"
    else
        echo -e "${YELLOW}○ ANTHROPIC_API_KEY not set in environment${NC}"
        echo -e "  Set it with: export ANTHROPIC_API_KEY=your-key-here"
    fi

    echo
}

# Install Python dependencies for pipeline
install_python_deps() {
    echo -e "${YELLOW}Installing Python dependencies...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        if command -v pip3 &> /dev/null; then
            pip3 install -r "$PROJECT_ROOT/requirements.txt"
            echo -e "${GREEN}✓ Python dependencies installed${NC}"
        else
            echo -e "${YELLOW}○ pip3 not found, skipping Python deps${NC}"
        fi
    fi

    echo
}

# Install custom skills
install_skills() {
    echo -e "${YELLOW}Installing custom skills...${NC}"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    SKILLS_DIR="$PROJECT_ROOT/openclaw/skills"

    if [ -d "$SKILLS_DIR/substack-pipeline" ]; then
        cd "$SKILLS_DIR/substack-pipeline"
        if [ -f "package.json" ]; then
            if [ "$PKG_MANAGER" = "pnpm" ]; then
                pnpm install
            else
                npm install
            fi
            echo -e "${GREEN}✓ Custom skills installed${NC}"
        fi
    fi

    echo
}

# Run onboarding
run_onboarding() {
    echo -e "${YELLOW}Running OpenClaw onboarding...${NC}"
    echo -e "This will configure the Gateway daemon."
    echo

    read -p "Run onboarding wizard? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        openclaw onboard --install-daemon
    else
        echo -e "${YELLOW}Skipping onboarding. Run 'openclaw onboard' later to complete setup.${NC}"
    fi

    echo
}

# Print summary
print_summary() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Setup Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo
    echo -e "${GREEN}OpenClaw is now configured for this project.${NC}"
    echo
    echo -e "Quick Start Commands:"
    echo -e "  ${YELLOW}openclaw gateway${NC}        - Start the gateway server"
    echo -e "  ${YELLOW}openclaw chat${NC}           - Start interactive chat"
    echo -e "  ${YELLOW}openclaw status${NC}         - Check status"
    echo
    echo -e "WebChat Dashboard: ${BLUE}http://127.0.0.1:18790${NC}"
    echo -e "Gateway WebSocket: ${BLUE}ws://127.0.0.1:18789${NC}"
    echo
    echo -e "Project-specific commands:"
    echo -e "  ${YELLOW}python -m pipeline.main run --input data/raw${NC}  - Run full pipeline"
    echo -e "  ${YELLOW}python -m pipeline.main search --query \"...\"${NC} - Search archive"
    echo
    echo -e "For GitHub integration, ensure you have:"
    echo -e "  1. GITHUB_TOKEN set (for PR creation)"
    echo -e "  2. Repository write access"
    echo
}

# Main execution
main() {
    check_dependencies
    install_openclaw
    configure_openclaw
    setup_environment
    install_python_deps
    install_skills
    run_onboarding
    print_summary
}

# Run with optional flags
case "${1:-}" in
    --skip-onboard)
        check_dependencies
        install_openclaw
        configure_openclaw
        setup_environment
        install_python_deps
        install_skills
        print_summary
        ;;
    --deps-only)
        check_dependencies
        install_python_deps
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo
        echo "Options:"
        echo "  --skip-onboard  Skip the interactive onboarding wizard"
        echo "  --deps-only     Only install Python dependencies"
        echo "  --help, -h      Show this help message"
        ;;
    *)
        main
        ;;
esac
