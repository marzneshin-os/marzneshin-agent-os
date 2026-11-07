---
description: Anthropic Skill Creator — Scaffold and optimize new SKILL.md (Khairallah Stack #25)
---

**ANTHROPIC SKILL CREATOR META-SKILL**

Generate a new, production-grade Claude Code skill:
1. **Skill Name**: Use kebab-case (e.g. `fastmcp-tools`, `db-migration`).
2. **Frontmatter**:
   - `name`: Human-readable identifier.
   - `description`: Crisp summary and trigger phrases.
   - `user-invocable`: `true` (for user slash command) or `false` (background rule).
3. **Progressive Disclosure**: Keep core `SKILL.md` under 400 lines; place heavy schemas or references in `references/` or `scripts/`.
4. **Location**: Place in `.claude/skills/<name>/SKILL.md`.