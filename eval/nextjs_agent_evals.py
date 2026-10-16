"""Next.js Agent Evals Benchmark Suite (nextjs.org/evals, Sep 25, 2026).

Implements the official evaluation tasks, pass@4 scoring, and telemetry
matrix for comparing AI models on Next.js 15+ coding challenges.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ModelEvalResult:
    name: str
    id: str
    pass4_rate: float
    pass1_rate: float
    cost_per_task_usd: float
    highlight: bool = False
    color: str = "#475569"
    badge: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "id": self.id,
            "pass4_rate": self.pass4_rate,
            "pass4_pct": f"{int(round(self.pass4_rate * 100))}%",
            "pass1_rate": self.pass1_rate,
            "pass1_pct": f"{int(round(self.pass1_rate * 100))}%",
            "cost_per_task_usd": self.cost_per_task_usd,
            "cost_display": "FREE" if self.cost_per_task_usd == 0 else f"${self.cost_per_task_usd:.2f}",
            "highlight": self.highlight,
            "color": self.color,
            "badge": self.badge,
        }


OFFICIAL_BENCHMARK_RESULTS: list[ModelEvalResult] = [
    ModelEvalResult(
        name="Claude Fable 5.1 (high)",
        id="claude-fable-5.1",
        pass4_rate=0.97,
        pass1_rate=0.885,
        cost_per_task_usd=0.72,
        color="#334155",
        badge="Top Quality",
    ),
    ModelEvalResult(
        name="Pixel Canary",
        id="stealth/pixel-canary",
        pass4_rate=0.90,
        pass1_rate=0.782,
        cost_per_task_usd=0.00,
        highlight=True,
        color="#f59e0b",
        badge="Best Value (FREE)",
    ),
    ModelEvalResult(
        name="GPT 6 Astra (high)",
        id="gpt-6-astra",
        pass4_rate=0.90,
        pass1_rate=0.794,
        cost_per_task_usd=0.89,
        color="#334155",
        badge="Tied #2",
    ),
    ModelEvalResult(
        name="Kimi K3",
        id="kimi-k3",
        pass4_rate=0.84,
        pass1_rate=0.710,
        cost_per_task_usd=0.28,
        color="#334155",
        badge="Budget Runner",
    ),
    ModelEvalResult(
        name="Claude Sonnet 5",
        id="claude-sonnet-5",
        pass4_rate=0.81,
        pass1_rate=0.685,
        cost_per_task_usd=0.39,
        color="#334155",
        badge="Reliable",
    ),
]


BENCHMARK_TASKS: list[dict[str, Any]] = [
    {
        "id": "NEXT-01",
        "title": "Server Action with Form Validation",
        "category": "Server Actions",
        "difficulty": "Medium",
        "prompt": "Create a Next.js Server Action in 'app/actions/user.ts' that validates email & name using Zod, writes to database, and calls revalidatePath('/users').",
        "required_checks": ["use server", "zod", "revalidatePath", "try", "catch"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 1},
            "gpt-6-astra": {"passed": True, "attempts": 1},
            "kimi-k3": {"passed": True, "attempts": 2},
            "claude-sonnet-5": {"passed": True, "attempts": 2},
        }
    },
    {
        "id": "NEXT-02",
        "title": "RSC Streaming with Suspense Skeleton",
        "category": "React Server Components",
        "difficulty": "Hard",
        "prompt": "Implement a parallel data fetching component in Next.js 15 using React Suspense and dynamic streaming for slow API dependencies.",
        "required_checks": ["Suspense", "fallback", "async", "await", "export default async function"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 2},
            "gpt-6-astra": {"passed": True, "attempts": 1},
            "kimi-k3": {"passed": True, "attempts": 3},
            "claude-sonnet-5": {"passed": True, "attempts": 3},
        }
    },
    {
        "id": "NEXT-03",
        "title": "Hydration Mismatch Resolution in ThemeProvider",
        "category": "SSR & Hydration",
        "difficulty": "Hard",
        "prompt": "Resolve a client/server timestamp and localStorage theme hydration mismatch in Next.js layout using suppressHydrationWarning or useEffect mounted state.",
        "required_checks": ["use client", "useEffect", "useState", "suppressHydrationWarning"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 1},
            "gpt-6-astra": {"passed": True, "attempts": 2},
            "kimi-k3": {"passed": False, "attempts": 4},
            "claude-sonnet-5": {"passed": True, "attempts": 3},
        }
    },
    {
        "id": "NEXT-04",
        "title": "Edge Route Handler with JWT Verification",
        "category": "Route Handlers",
        "difficulty": "Medium",
        "prompt": "Implement 'app/api/auth/route.ts' running on Edge runtime with NextRequest, NextResponse, Bearer token extraction, and jose JWT validation.",
        "required_checks": ["export const runtime = 'edge'", "NextRequest", "NextResponse", "Authorization"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 1},
            "gpt-6-astra": {"passed": True, "attempts": 1},
            "kimi-k3": {"passed": True, "attempts": 2},
            "claude-sonnet-5": {"passed": True, "attempts": 2},
        }
    },
    {
        "id": "NEXT-05",
        "title": "Intercepting Route & Modal Navigation",
        "category": "App Router Routing",
        "difficulty": "Expert",
        "prompt": "Create an intercepting modal route '(.)photo/[id]' that renders inside parallel slot '@modal' while preserving URL sharability.",
        "required_checks": ["@modal", "(.)photo", "useRouter", "router.back()", "children"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 2},
            "gpt-6-astra": {"passed": True, "attempts": 2},
            "kimi-k3": {"passed": True, "attempts": 4},
            "claude-sonnet-5": {"passed": False, "attempts": 4},
        }
    },
    {
        "id": "NEXT-06",
        "title": "Next.js 15 Async Request APIs Migration",
        "category": "Framework Upgrades",
        "difficulty": "Hard",
        "prompt": "Migrate page params, searchParams, and cookies() calls from synchronous to Promise-based async pattern per Next.js 15 breaking changes.",
        "required_checks": ["await params", "await searchParams", "await cookies()", "async function Page"],
        "model_results": {
            "claude-fable-5.1": {"passed": True, "attempts": 1},
            "stealth/pixel-canary": {"passed": True, "attempts": 1},
            "gpt-6-astra": {"passed": True, "attempts": 1},
            "kimi-k3": {"passed": True, "attempts": 3},
            "claude-sonnet-5": {"passed": True, "attempts": 3},
        }
    },
]


def score_code_snippet(code: str, required_checks: list[str]) -> dict[str, Any]:
    matched = [c for c in required_checks if c.lower() in code.lower()]
    missing = [c for c in required_checks if c.lower() not in code.lower()]
    score = len(matched) / max(1, len(required_checks))
    return {
        "score": score,
        "passed": score >= 0.75,
        "matched": matched,
        "missing": missing,
    }


def export_benchmark_data(output_path: Path | None = None) -> dict[str, Any]:
    data = {
        "title": "Next.js Agent Evals: Success Rate (pass@4)",
        "source": "nextjs.org/evals, Sep 25, 2026",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": [m.to_dict() for m in OFFICIAL_BENCHMARK_RESULTS],
        "tasks": BENCHMARK_TASKS,
        "metadata": {
            "highlight_model": "Pixel Canary",
            "highlight_reason": "Tied with GPT 6 Astra (90%) with $0.00 cost (100% Free via Cline)",
            "benchmark_version": "v4.0.0",
            "tasks_count": len(BENCHMARK_TASKS),
        }
    }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return data


if __name__ == "__main__":
    out_file = Path("/home/asus/code/marzneshin-agent-os/dashboards/nextjs-agent-evals/data.json")
    export_benchmark_data(out_file)
    print(f"Exported benchmark data to {out_file}")
