#!/usr/bin/env bash
# ==============================================================================
# Marzneshin Agent OS - Core AI Tooling Manager
# Controls: AgentMemory, Headroom, Codeburn, Graphify, Kimi K3
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

ACTION="${1:-status}"

case "$ACTION" in
    start)
        echo "Starting AgentMemory, Headroom, Codeburn, Graphify, Kimi K3, and Kimi K3..."
        python3 scripts/dev.py start --tools
        ;;
    stop)
        echo "Stopping core AI tools..."
        python3 scripts/dev.py stop --tools
        ;;
    restart)
        echo "Restarting core AI tools..."
        python3 scripts/dev.py restart --tools
        ;;
    status)
        python3 scripts/dev.py status
        ;;
    test)
        echo "Running ecosystem health checks..."
        python3 scripts/test_ecosystem.py
        ;;
    *)
        echo "Usage: ./scripts/tools.sh {start|status|stop|restart|test}"
        exit 1
        ;;
esac
