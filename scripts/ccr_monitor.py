#!/usr/bin/env python3
"""
CCR Live Monitor — Watch which model is responding in real-time.
Shows the last N requests with: timestamp, requested model, actual provider/model, status, duration.

Usage:
  python3 scripts/ccr_monitor.py          # show last 10 requests
  python3 scripts/ccr_monitor.py --watch  # live tail (refreshes every 3 seconds)
  python3 scripts/ccr_monitor.py -n 20    # show last 20 requests
"""
import sqlite3, json, sys, time, os, shutil

WINDOWS_APP_DIR = "/mnt/c/Users/Asus/AppData/Roaming/claude-code-router"
WIN_LOCAL_DIR = r"C:\Users\Asus\AppData\Roaming\claude-code-router"
LINUX_DIR = os.path.expanduser("~/.claude-code-router")

TMP_DIR = "/tmp/ccr_logs"

def get_db_path():
    if os.name == "nt":
        return os.path.join(WIN_LOCAL_DIR, "request-logs.sqlite")
    if os.path.exists(WINDOWS_APP_DIR):
        os.makedirs(TMP_DIR, exist_ok=True)
        # Copy db files to Linux filesystem to avoid drvfs SQLite WAL lock issues
        for ext in ["", "-wal", "-shm"]:
            src = os.path.join(WINDOWS_APP_DIR, f"request-logs.sqlite{ext}")
            dst = os.path.join(TMP_DIR, f"request-logs.sqlite{ext}")
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dst)
                except Exception:
                    pass
        return os.path.join(TMP_DIR, "request-logs.sqlite")
    
    # Fallback to linux native dir
    for candidate in [
        os.path.join(LINUX_DIR, "request-logs.sqlite"),
        os.path.join(LINUX_DIR, "app-data", "request-logs.sqlite")
    ]:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(TMP_DIR, "request-logs.sqlite")

def get_recent(n=10):
    db_file = get_db_path()
    if not os.path.exists(db_file):
        return []
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"""
            SELECT 
                id,
                created_at,
                completed_at,
                client,
                provider,
                model,
                requested_model,
                resolved_model,
                response_model,
                status_code,
                ok,
                duration_ms,
                input_tokens,
                output_tokens,
                reasoning_tokens,
                is_stream,
                path
            FROM request_logs
            ORDER BY id DESC
            LIMIT {n}
        """).fetchall()
        conn.close()
        return rows
    except Exception as e:
        return []

def format_row(r):
    status = "✅" if r["ok"] else ("❌" if r["status_code"] and r["status_code"] >= 400 else "⏳")
    
    actual = r["response_model"] or r["resolved_model"] or r["model"] or "?"
    requested = r["requested_model"] or r["model"] or "?"
    provider = r["provider"] or "?"
    
    duration = f"{r['duration_ms']}ms" if r["duration_ms"] else "..."
    tokens = ""
    if r["input_tokens"] or r["output_tokens"]:
        tokens = f" [{r['input_tokens'] or '?'}→{r['output_tokens'] or '?'}"
        if r["reasoning_tokens"]:
            tokens += f" 🧠{r['reasoning_tokens']}"
        tokens += "]"
    
    ts = (r["created_at"] or "")[:19].replace("T", " ")
    stream = "🔄" if r["is_stream"] else "📦"
    
    return f"{status} {ts} | {stream} {provider}/{actual:<28} | ⏱{duration:<8}{tokens:<16} | req: {requested}"

def main():
    watch = "--watch" in sys.argv or "-w" in sys.argv
    n = 10
    for i, arg in enumerate(sys.argv):
        if arg == "-n" and i + 1 < len(sys.argv):
            n = int(sys.argv[i + 1])

    if watch:
        last_id = 0
        print("🔍 CCR Live Monitor — watching for new requests (Ctrl+C to stop)\n")
        while True:
            rows = get_recent(n)
            if rows:
                newest_id = rows[0]["id"]
                if newest_id != last_id:
                    os.system("clear" if os.name != "nt" else "cls")
                    print("🔍 CCR Live Monitor — real-time request log\n")
                    print(f"{'Status':<4} {'Timestamp':<20} | {'Provider/Actual Model':<47} | {'Duration':<8} {'Tokens':<16} | {'Requested'}")
                    print("-" * 125)
                    for r in reversed(rows):
                        print(format_row(r))
                    print(f"\n🕐 Last refresh: {time.strftime('%H:%M:%S')}")
                    last_id = newest_id
            time.sleep(2)  # clock-ok
    else:
        rows = get_recent(n)
        if not rows:
            print("No requests logged yet.")
            return
        print(f"🔍 CCR — Last {len(rows)} requests\n")
        print(f"{'Status':<4} {'Timestamp':<20} | {'Provider/Actual Model':<47} | {'Duration':<8} {'Tokens':<16} | {'Requested'}")
        print("-" * 125)
        for r in reversed(rows):
            print(format_row(r))

if __name__ == "__main__":
    main()
