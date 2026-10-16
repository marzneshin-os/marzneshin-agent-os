#!/usr/bin/env bash
# ==============================================================================
# Atria-Dawn-Preview Claude Code Launcher (High-Tech Runner)
# Connects Claude Code CLI to Shanghai AI Lab's 744B MoE Atria-Dawn Engine
# ==============================================================================

set -e

# Styling definitions
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.atria"

echo -e "${CYAN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║             ⚡ ATRIA-DAWN CLAUDE CODE RUNNER ⚡                  ║"
echo "║          744B MoE Agentic Intelligence (100M Free Tokens)        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 1. Load Environment Configuration
if [ -f "$ENV_FILE" ]; then
    # Load keys ignoring comments
    export $(grep -v '^#' "$ENV_FILE" | xargs -d '\n' -r) 2>/dev/null || true
fi

KEY="${ATRIA_API_KEY:-$ANTHROPIC_AUTH_TOKEN}"

# 2. Check for API Key
if [ -z "$KEY" ]; then
    echo -e "${YELLOW}[!] ATRIA_API_KEY not found in .env.atria${NC}"
    echo -e "You can get 100M free tokens at: ${CYAN}https://api.atria-asi.ai${NC}"
    echo ""
    read -rp "Please enter your Atria API Key: " INPUT_KEY
    if [ -n "$INPUT_KEY" ]; then
        KEY="$INPUT_KEY"
        # Persist to .env.atria
        echo "ATRIA_API_KEY=\"$KEY\"" >> "$ENV_FILE"
        echo "ANTHROPIC_AUTH_TOKEN=\"$KEY\"" >> "$ENV_FILE"
        echo -e "${GREEN}[✓] API Key saved to .env.atria${NC}"
    else
        echo -e "${RED}[✗] Error: API Key is required to run Atria-Dawn.${NC}"
        exit 1
    fi
fi

# 3. Connectivity Verification
echo -e "${CYAN}[*] Verifying connectivity to Atria Gateway (api.atria-asi.ai)...${NC}"
if curl -s -m 4 https://api.atria-asi.ai > /dev/null; then
    echo -e "${GREEN}[✓] Gateway reachable.${NC}"
else
    echo -e "${YELLOW}[!] Warning: Gateway ping took longer than expected or was unreachable. Continuing anyway...${NC}"
fi

# 4. Set Environment Variables for Claude Code
export ANTHROPIC_BASE_URL="https://api.atria-asi.ai"
export ANTHROPIC_AUTH_TOKEN="$KEY"
export ANTHROPIC_API_KEY="$KEY"

echo ""
echo -e "${BOLD}Target Model:${NC}     ${GREEN}Atria-Dawn-Preview (744B MoE)${NC}"
echo -e "${BOLD}Base URL:${NC}         ${GREEN}https://api.atria-asi.ai${NC}"
echo -e "${BOLD}Project Context:${NC}  ${CYAN}${PROJECT_ROOT}${NC}"
echo ""
echo -e "${GREEN}${BOLD}>> Launching Claude Code CLI with Atria Backend...${NC}"
echo -e "──────────────────────────────────────────────────────────────────"

# 5. Check if local claude binary or npx is preferred
cd "$PROJECT_ROOT"

if command -v claude &> /dev/null; then
    exec claude --model Atria-Dawn-Preview "$@"
elif [ -x "$HOME/.local/bin/claude" ]; then
    exec "$HOME/.local/bin/claude" --model Atria-Dawn-Preview "$@"
else
    exec npx @anthropic-ai/claude-code --model Atria-Dawn-Preview "$@"
fi
