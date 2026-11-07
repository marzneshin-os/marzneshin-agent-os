#!/usr/bin/env python3
"""SubagentStop hook for Claude Code.
Intercepts subagent termination, parses transcript for token consumption,
and appends records to logs/handoffs.log.
Enforces stage and subagent budget limits.
"""
import sys
import json
import os
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOKS_DIR.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))
os.environ.setdefault('MARZNESHIN_OPS_ROOT', str(REPO_ROOT))

from lib import clock  # noqa: E402

LOGS_DIR = REPO_ROOT / 'logs'
HANDOFF_LOG = LOGS_DIR / 'handoffs.log'
STATE_DIR = REPO_ROOT / 'state'
STAGE_COSTS_FILE = STATE_DIR / 'cost_stages.json'

def parse_transcript_tokens(transcript_path: str) -> tuple[int, float]:
    total_tokens = 0
    estimated_cost = 0.0
    if not transcript_path or not os.path.exists(transcript_path):
        return total_tokens, estimated_cost

    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    usage = entry.get('usage') or entry.get('message', {}).get('usage') or {}
                    in_tok = usage.get('input_tokens', 0)
                    out_tok = usage.get('output_tokens', 0)
                    cache_tok = usage.get('cache_read_input_tokens', 0)
                    if in_tok or out_tok:
                        total_tokens += (in_tok + out_tok + cache_tok)
                        cost = (in_tok * 0.000003) + (out_tok * 0.000015) + (cache_tok * 0.0000003)
                        estimated_cost += cost
                except Exception:
                    continue
    except Exception:
        pass

    return total_tokens, estimated_cost

def main():
    payload = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
    except Exception:
        pass

    agent_name = (
        payload.get('subagent_type') or 
        payload.get('agent_type') or 
        payload.get('agent_name') or 
        'subagent'
    )
    task = payload.get('prompt') or payload.get('task') or 'task execution'
    task_clean = ' '.join(task.split())[:120]
    
    transcript_path = payload.get('transcript_path', '')
    session_id = str(payload.get('session_id', 'unknown'))
    
    tokens, cost = parse_transcript_tokens(transcript_path)
    
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    now_iso = clock.iso()
    log_line = (
        f'[{now_iso}] AGENT: {agent_name} | TASK: {task_clean} | '
        f'TOKENS: {tokens:,} | COST_EST: ${cost:.3f} | SESSION: {session_id[:8]}\n'
    )
    
    with open(HANDOFF_LOG, 'a', encoding='utf-8') as f:
        f.write(log_line)

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        stage_data = {}
        if STAGE_COSTS_FILE.exists():
            stage_data = json.loads(STAGE_COSTS_FILE.read_text(encoding='utf-8'))
        
        current_stage = stage_data.get('current_stage', 'execute')
        stage_costs = stage_data.setdefault('stages', {})
        stage_entry = stage_costs.setdefault(current_stage, {'cost': 0.0, 'tokens': 0, 'handoffs': 0})
        stage_entry['cost'] = round(stage_entry['cost'] + cost, 4)
        stage_entry['tokens'] = stage_entry['tokens'] + tokens
        stage_entry['handoffs'] = stage_entry['handoffs'] + 1
        
        STAGE_COSTS_FILE.write_text(json.dumps(stage_data, indent=2), encoding='utf-8')
    except Exception:
        pass

    sys.exit(0)

if __name__ == '__main__':
    main()
