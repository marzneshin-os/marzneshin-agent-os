#!/usr/bin/env python3
"""Cline Setup Script for Pixel Canary (BUILD-SPEC §9).

Configures Cline Desktop and Cline VS Code extension to use the free
stealth model `stealth/pixel-canary` via Vercel AI Gateway (90% Next.js evals).
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Route all timestamps through lib/clock per D6 invariant
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import clock


def get_cline_data_dirs() -> list[Path]:
    paths = []
    # Windows paths
    userprofile = os.getenv("USERPROFILE")
    if userprofile:
        p1 = Path(userprofile) / ".cline" / "data"
        if p1.exists():
            paths.append(p1)

    appdata = os.getenv("APPDATA")
    if appdata:
        p2 = Path(appdata) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev"
        if p2.exists():
            paths.append(p2)

    # WSL / Linux mapped paths
    home = Path.home()
    p_linux = home / ".cline" / "data"
    if p_linux.exists():
        paths.append(p_linux)

    # WSL access to Windows UserProfile
    mnt_c = Path("/mnt/c/Users")
    if mnt_c.exists():
        for user_dir in mnt_c.iterdir():
            cline_dir = user_dir / ".cline" / "data"
            if cline_dir.exists() and cline_dir not in paths:
                paths.append(cline_dir)

    return paths


def configure_cline(target_dir: Path, activate: bool = False, base_url: str = "https://ai-gateway.vercel.sh/v1"):
    print(f"[*] Configuring Cline in: {target_dir}")
    settings_dir = target_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)

    timestamp = clock.now().strftime("%Y%m%d_%H%M%S")

    # 1. Update providers.json
    providers_file = settings_dir / "providers.json"
    providers_data = {"version": 1, "lastUsedProvider": "openai-compatible", "providers": {}}
    if providers_file.exists():
        try:
            with open(providers_file, "r", encoding="utf-8") as f:
                providers_data = json.load(f)
            shutil.copy2(providers_file, settings_dir / f"providers.json.bak_{timestamp}")
        except Exception as e:
            print(f"    [!] Warning reading providers.json: {e}")

    providers_data.setdefault("providers", {})
    providers_data["providers"]["pixel-canary"] = {
        "settings": {
            "provider": "openai-compatible",
            "model": "stealth/pixel-canary",
            "baseUrl": base_url,
            "apiKey": "free",
            "headers": {
                "HTTP-Referer": "https://marzneshin.os",
                "X-Title": "Marzneshin Autonomous OS"
            }
        },
        "updatedAt": clock.to_iso(clock.now()),
        "tokenSource": "manual"
    }

    with open(providers_file, "w", encoding="utf-8") as f:
        json.dump(providers_data, f, indent=2)
    print("    [+] Updated providers.json (added pixel-canary)")

    # 2. Update models.json
    models_file = settings_dir / "models.json"
    models_data = {"version": 1, "providers": {}}
    if models_file.exists():
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                models_data = json.load(f)
            shutil.copy2(models_file, settings_dir / f"models.json.bak_{timestamp}")
        except Exception as e:
            print(f"    [!] Warning reading models.json: {e}")

    models_data.setdefault("providers", {})
    models_data["providers"]["pixel-canary"] = {
        "provider": {
            "name": "Pixel Canary (Free - 90% Next.js Evals)",
            "baseUrl": base_url,
            "defaultModelId": "stealth/pixel-canary"
        },
        "models": {
            "stealth/pixel-canary": {
                "id": "stealth/pixel-canary",
                "name": "Pixel Canary (Stealth - 90% Pass@4)",
                "contextWindow": 128000,
                "maxInputTokens": 128000,
                "capabilities": ["streaming", "tools", "images"]
            }
        }
    }

    with open(models_file, "w", encoding="utf-8") as f:
        json.dump(models_data, f, indent=2)
    print("    [+] Updated models.json (added stealth/pixel-canary profile)")

    # 3. Update globalState.json if activate requested
    global_state_file = target_dir / "globalState.json"
    if global_state_file.exists():
        try:
            with open(global_state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            shutil.copy2(global_state_file, target_dir / f"globalState.json.bak_{timestamp}")

            if activate:
                state_data["openAiBaseUrl"] = base_url
                state_data["planModeOpenAiModelId"] = "stealth/pixel-canary"
                state_data["actModeOpenAiModelId"] = "stealth/pixel-canary"
                state_data["planModeApiProvider"] = "openai"
                state_data["actModeApiProvider"] = "openai"

                with open(global_state_file, "w", encoding="utf-8") as f:
                    json.dump(state_data, f, indent=2)
                print("    [+] Activated stealth/pixel-canary in globalState.json for Plan & Act modes!")
            else:
                print("    [*] Kept current active model unchanged (use --activate to set as default).")
        except Exception as e:
            print(f"    [!] Warning updating globalState.json: {e}")


def main():
    parser = argparse.ArgumentParser(description="Configure Cline for Pixel Canary")
    parser.add_argument("--activate", action="store_true", help="Set Pixel Canary as default active model in Cline")
    parser.add_argument("--base-url", default="https://ai-gateway.vercel.sh/v1", help="Custom Gateway Base URL")
    args = parser.parse_args()

    dirs = get_cline_data_dirs()
    if not dirs:
        print("[!] No Cline installation directories found.")
        sys.exit(1)

    print(f"[*] Found {len(dirs)} Cline data directories.")
    for d in dirs:
        configure_cline(d, activate=args.activate, base_url=args.base_url)

    print("\n[✔] Cline configuration for Pixel Canary complete!")
    print("    Model: stealth/pixel-canary")
    print(f"    Gateway URL: {args.base_url}")
    print("    Next.js Agent Evals Benchmark: 90% pass@4 (FREE)")


if __name__ == "__main__":
    main()
