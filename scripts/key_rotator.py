#!/usr/bin/env python3
"""
CCR Smart Key Pool & Auto-Rotator Daemon
=========================================
Monitors Claude Code Router request logs in real-time.
When an API key is depleted (HTTP 402 / 429 / Quota Error), it automatically:
  1. Marks current key as depleted in configs/keys_pool.json.
  2. Picks the next available key from the pool.
  3. Updates Windows CCR config.sqlite and WSL config.sqlite.
  4. Updates configs/router.json.
  5. Restarts CCR daemon seamlessly without stopping the workflow.

CLI Usage:
  python3 scripts/key_rotator.py --status           # View pool status & active keys
  python3 scripts/key_rotator.py --add-key <key>    # Add a new HuggingFace token to pool
  python3 scripts/key_rotator.py --rotate           # Force immediate rotation to next key
  python3 scripts/key_rotator.py --watch            # Run daemon monitoring in background
"""

import os
import sys
import json
import time
import shutil
import sqlite3
import subprocess
from datetime import datetime

# Path definitions (WSL & Windows compatible)
IS_WIN = os.name == "nt"

if IS_WIN:
    REPO_DIR = r"C:\Users\Asus\code\marzneshin-agent-os"
    WIN_APPDATA_DIR = r"C:\Users\Asus\AppData\Roaming\claude-code-router"
    WIN_CONFIG_SQLITE = os.path.join(WIN_APPDATA_DIR, "config.sqlite")
    WIN_LOGS_SQLITE = os.path.join(WIN_APPDATA_DIR, "request-logs.sqlite")
    WSL_CONFIG_SQLITE = None
else:
    REPO_DIR = "/home/asus/code/marzneshin-agent-os"
    WIN_APPDATA_DIR = "/mnt/c/Users/Asus/AppData/Roaming/claude-code-router"
    WIN_CONFIG_SQLITE = os.path.join(WIN_APPDATA_DIR, "config.sqlite")
    WIN_LOGS_SQLITE = os.path.join(WIN_APPDATA_DIR, "request-logs.sqlite")
    WSL_CONFIG_SQLITE = os.path.expanduser("~/.claude-code-router/config.sqlite")

POOL_FILE = os.path.join(REPO_DIR, "configs", "keys_pool.json")
ROUTER_FILE = os.path.join(REPO_DIR, "configs", "router.json")
TMP_DIR = "/tmp/ccr_rotator" if not IS_WIN else os.path.join(os.environ.get("TEMP", "C:\\Temp"), "ccr_rotator")

def load_pool():
    if os.path.exists(POOL_FILE):
        try:
            with open(POOL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {POOL_FILE}: {e}")
    return {
        "HuggingFace": {
            "active_key": "",
            "pool": [],
            "depleted": []
        }
    }

def save_pool(pool_data):
    os.makedirs(os.path.dirname(POOL_FILE), exist_ok=True)
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool_data, f, indent=4)

def mask_key(k):
    if not k:
        return "(none)"
    if len(k) <= 12:
        return k
    return f"{k[:8]}...{k[-4:]}"

def get_recent_errors(limit=10):
    """Safely reads request_logs using a temporary copy to avoid drvfs lock issues."""
    if not os.path.exists(WIN_LOGS_SQLITE):
        return []
    
    os.makedirs(TMP_DIR, exist_ok=True)
    tmp_db = os.path.join(TMP_DIR, "request-logs.sqlite")
    
    # Copy sqlite files
    for ext in ["", "-wal", "-shm"]:
        src = f"{WIN_LOGS_SQLITE}{ext}"
        dst = f"{tmp_db}{ext}"
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
                
    if not os.path.exists(tmp_db):
        return []

    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute("""
            SELECT id, created_at, provider, model, requested_model, status_code, ok, error 
            FROM request_logs 
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return rows
    except Exception as e:
        return []

def update_sqlite_token(db_path, new_token):
    if not db_path or not os.path.exists(db_path):
        return False
    if db_path.startswith("/mnt/c"):
        win_path = db_path.replace("/mnt/c/", "C:\\").replace("/", "\\")
        py_cmd = (
            f"import sqlite3, json; "
            f"conn = sqlite3.connect(r'{win_path}'); "
            f"cur = conn.cursor(); "
            f"cur.execute(\\\"SELECT value_json FROM app_config WHERE key='default'\\\"); "
            f"row = cur.fetchone(); "
            f"cfg = json.loads(row[0]); "
            f"providers = cfg.get('Providers', []); "
            f"updated = False; "
            f"for p in providers: "
            f"    if p.get('name') == 'HuggingFace': "
            f"        p['api_key'] = '{new_token}'; updated = True\n"
            f"if updated: "
            f"    cur.execute(\\\"UPDATE app_config SET value_json = ? WHERE key='default'\\\", (json.dumps(cfg, indent=2),)); "
            f"    conn.commit()\n"
            f"conn.close()"
        )
        try:
            res = subprocess.run(["powershell.exe", "-NoProfile", "-Command", f'py -c "{py_cmd}"'], capture_output=True, text=True)
            return res.returncode == 0
        except Exception as e:
            print(f"⚠️ PowerShell py error: {e}")
            return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT value_json FROM app_config WHERE key='default'")
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
            
        cfg = json.loads(row[0])
        providers = cfg.get("Providers", [])
        updated = False
        
        if isinstance(providers, list):
            for p in providers:
                if p.get("name") == "HuggingFace":
                    p["api_key"] = new_token
                    updated = True
        elif isinstance(providers, dict):
            if "HuggingFace" in providers:
                providers["HuggingFace"]["api_key"] = new_token
                updated = True
                
        if updated:
            cur.execute("UPDATE app_config SET value_json = ? WHERE key='default'", (json.dumps(cfg, indent=2),))
            conn.commit()
        conn.close()
        return updated
    except Exception as e:
        print(f"⚠️ Error updating SQLite ({db_path}): {e}")
        return False

def update_router_json_token(new_token):
    if not os.path.exists(ROUTER_FILE):
        return False
    try:
        with open(ROUTER_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "huggingface" in cfg.get("gateways", {}):
            cfg["gateways"]["huggingface"]["base_url"] = "https://router.huggingface.co/v1"
            cfg["gateways"]["huggingface"]["api_key"] = f"${{HF_API_KEY:-{new_token}}}"
            with open(ROUTER_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            return True
    except Exception as e:
        print(f"⚠️ Error updating router.json: {e}")
    return False

def restart_ccr():
    """Restarts CCR daemon via Windows PowerShell."""
    print("🔄 Restarting Claude Code Router...")
    cmd = (
        'powershell.exe -NoProfile -Command "'
        'Stop-Process -Name \'*Claude Code Router*\' -Force -ErrorAction SilentlyContinue; '
        'Start-Sleep -Seconds 2; '
        '& \'C:\\Users\\Asus\\AppData\\Roaming\\claude-code-router\\bin\\ccr-app.cmd\' serve --no-open"'
    )
    try:
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)  # clock-ok
        print("✅ Claude Code Router restarted with new configuration.")
        return True
    except Exception as e:
        print(f"⚠️ Failed to restart CCR: {e}")
        return False

def rotate_key(reason="Depleted / Quota reached"):
    pool_data = load_pool()
    hf_data = pool_data.setdefault("HuggingFace", {"active_key": "", "pool": [], "depleted": []})
    
    current_key = hf_data.get("active_key", "")
    pool = hf_data.get("pool", [])
    depleted = hf_data.get("depleted", [])
    
    # Mark current as depleted
    if current_key and current_key not in depleted:
        depleted.append(current_key)
        print(f"🚫 Marked key {mask_key(current_key)} as DEPLETED ({reason})")
        
    # Find next available key
    next_key = None
    for k in pool:
        if k not in depleted:
            next_key = k
            break
            
    if not next_key:
        print("\n" + "!" * 80)
        print("🚨 CRITICAL: All Hugging Face keys in the pool have been depleted!")
        print("👉 Please add fresh tokens with:")
        print("   python3 scripts/key_rotator.py --add-key hf_YourNewToken")
        print("!" * 80 + "\n")
        save_pool(pool_data)
        return False
        
    print(f"✨ Found fresh key in pool: {mask_key(next_key)}")
    hf_data["active_key"] = next_key
    save_pool(pool_data)
    
    # Apply to config databases
    up_win = update_sqlite_token(WIN_CONFIG_SQLITE, next_key)
    up_wsl = update_sqlite_token(WSL_CONFIG_SQLITE, next_key)
    up_rtr = update_router_json_token(next_key)
    
    print(f"📁 Updated Windows DB: {'✅' if up_win else '❌'} | WSL DB: {'✅' if up_wsl else '❌'} | router.json: {'✅' if up_rtr else '❌'}")
    
    # Restart CCR
    restart_ccr()
    
    remaining = len([k for k in pool if k not in depleted])
    print(f"🎉 Successfully switched to new key {mask_key(next_key)}! ({remaining} keys remaining in pool)")
    return True

def print_status():
    pool_data = load_pool()
    hf_data = pool_data.get("HuggingFace", {})
    active = hf_data.get("active_key", "")
    pool = hf_data.get("pool", [])
    depleted = hf_data.get("depleted", [])
    available = [k for k in pool if k not in depleted]
    
    print("=" * 60)
    print("🔑 Claude Code Router — Hugging Face Key Pool Status")
    print("=" * 60)
    print(f"  🟢 Active Key   : {mask_key(active)}")
    print(f"  📦 Pool Total   : {len(pool)} keys")
    print(f"  ⚡ Available    : {len(available)} keys")
    print(f"  ❌ Depleted     : {len(depleted)} keys")
    print("-" * 60)
    if available:
        print("Available in queue:")
        for idx, k in enumerate(available, 1):
            is_cur = " (ACTIVE)" if k == active else ""
            print(f"  [{idx}] {mask_key(k)}{is_cur}")
    else:
        print("⚠️ No spare keys available in pool! Add more keys using:")
        print("   python3 scripts/key_rotator.py --add-key hf_...")
    print("=" * 60)

def add_key(key):
    key = key.strip()
    if not key.startswith("hf_"):
        print("❌ Invalid token format! Hugging Face tokens must start with 'hf_'")
        return False
    pool_data = load_pool()
    hf_data = pool_data.setdefault("HuggingFace", {"active_key": "", "pool": [], "depleted": []})
    
    pool = hf_data.setdefault("pool", [])
    depleted = hf_data.setdefault("depleted", [])
    
    # If in depleted, remove from depleted
    if key in depleted:
        depleted.remove(key)
        
    if key not in pool:
        pool.append(key)
        print(f"✅ Added token {mask_key(key)} to Hugging Face pool.")
    else:
        print(f"ℹ️ Token {mask_key(key)} already in pool.")
        
    if not hf_data.get("active_key"):
        hf_data["active_key"] = key
        
    save_pool(pool_data)
    print_status()
    return True

def watch_loop():
    print("👀 CCR Auto-Rotator Daemon active and watching logs...")
    print_status()
    last_checked_id = 0
    
    # Initialize with newest id
    recent = get_recent_errors(1)
    if recent:
        last_checked_id = recent[0]["id"]
        
    while True:
        try:
            rows = get_recent_errors(5)
            for r in reversed(rows):
                req_id = r["id"]
                if req_id > last_checked_id:
                    last_checked_id = req_id
                    status = r["status_code"]
                    provider = r["provider"] or ""
                    err_msg = str(r["error"] or "")
                    
                    # Detect HuggingFace depletion
                    is_hf = "huggingface" in provider.lower() or "huggingface" in (r["requested_model"] or "").lower()
                    is_depleted = (
                        status == 402 or
                        status == 429 or
                        "depleted your monthly included credits" in err_msg or
                        "Payment Required" in err_msg
                    )
                    
                    if is_hf and is_depleted:
                        print(f"\n⚠️ [{datetime.now().strftime('%H:%M:%S')}] Detected quota depletion on request #{req_id} ({status})")  # clock-ok
                        rotate_key(reason=f"HTTP {status} - Credits depleted")
                        # Sleep a moment to let CCR stabilize
                        time.sleep(6)  # clock-ok
                        break
            time.sleep(3)  # clock-ok
        except KeyboardInterrupt:
            print("\nStopping Auto-Rotator Daemon.")
            break
        except Exception as e:
            time.sleep(5)  # clock-ok

def main():
    if "--status" in sys.argv:
        print_status()
    elif "--add-key" in sys.argv:
        idx = sys.argv.index("--add-key")
        if idx + 1 < len(sys.argv):
            add_key(sys.argv[idx + 1])
        else:
            print("❌ Please provide the key: --add-key hf_...")
    elif "--rotate" in sys.argv:
        rotate_key(reason="Manual trigger")
    elif "--watch" in sys.argv or "--daemon" in sys.argv:
        watch_loop()
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
