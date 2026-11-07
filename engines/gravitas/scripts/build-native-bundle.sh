#!/usr/bin/env bash
# Build the tracked Antigravity plugin bundle from canonical sources.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bundle="$repo_root/dist/gravitas-antigravity"

if [[ "$bundle" != "$repo_root/dist/gravitas-antigravity" ]]; then
  echo "Refusing unexpected bundle path: $bundle" >&2
  exit 1
fi

rm -rf "$bundle"
mkdir -p "$bundle/scripts" "$bundle/skills" "$bundle/agents" "$bundle/rules"

cp "$repo_root/plugins/gravitas-antigravity/plugin.json" "$bundle/plugin.json"
cp "$repo_root/plugins/gravitas-antigravity/hooks.json" "$bundle/hooks.json"
cp -R "$repo_root/plugins/gravitas-antigravity/scripts/." "$bundle/scripts/"
cp -R "$repo_root/skills/gravitas" "$bundle/skills/gravitas"
cp -R "$repo_root/skills/gravitas-highstakes" "$bundle/skills/gravitas-highstakes"
cp -R "$repo_root/plugins/gravitas-antigravity/agents/." "$bundle/agents/"
cp -R "$repo_root/plugins/gravitas-antigravity/rules/." "$bundle/rules/"

find "$bundle" -type d -name '__pycache__' -prune -exec rm -rf {} +
# Deterministic content manifest: sorted relative paths + sha256, so drift
# review distinguishes real changes from rebuild noise.
python3 - "$bundle" <<'EOF'
import hashlib
import sys
from pathlib import Path
bundle = Path(sys.argv[1])
lines = []
for path in sorted(bundle.rglob("*")):
    if path.is_file() and path.name != "SHA256SUMS":
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(bundle).as_posix()}")
(bundle / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
EOF
echo "Built $bundle"
