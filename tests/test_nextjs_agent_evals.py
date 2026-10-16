"""Tests for Next.js Agent Evals Benchmark Suite (BUILD-SPEC §4)."""

import unittest
from eval.nextjs_agent_evals import (
    OFFICIAL_BENCHMARK_RESULTS,
    BENCHMARK_TASKS,
    score_code_snippet,
    export_benchmark_data,
)


class TestNextjsAgentEvals(unittest.TestCase):
    def test_benchmark_models_matrix(self):
        self.assertEqual(len(OFFICIAL_BENCHMARK_RESULTS), 5)
        names = [m.name for m in OFFICIAL_BENCHMARK_RESULTS]
        self.assertIn("Claude Fable 5.1 (high)", names)
        self.assertIn("Pixel Canary", names)
        self.assertIn("GPT 6 Astra (high)", names)
        self.assertIn("Kimi K3", names)
        self.assertIn("Claude Sonnet 5", names)

    def test_pixel_canary_benchmark_scores(self):
        pixel = next(m for m in OFFICIAL_BENCHMARK_RESULTS if m.name == "Pixel Canary")
        self.assertEqual(pixel.pass4_rate, 0.90)
        self.assertEqual(pixel.cost_per_task_usd, 0.00)
        self.assertTrue(pixel.highlight)
        self.assertEqual(pixel.color, "#f59e0b")

        gpt6 = next(m for m in OFFICIAL_BENCHMARK_RESULTS if m.name == "GPT 6 Astra (high)")
        self.assertEqual(gpt6.pass4_rate, 0.90)
        self.assertEqual(gpt6.cost_per_task_usd, 0.89)

        fable = next(m for m in OFFICIAL_BENCHMARK_RESULTS if m.name == "Claude Fable 5.1 (high)")
        self.assertEqual(fable.pass4_rate, 0.97)
        self.assertEqual(fable.cost_per_task_usd, 0.72)

    def test_code_scoring(self):
        valid_code = """
        'use server';
        import { z } from 'zod';
        import { revalidatePath } from 'next/cache';
        export async function submitAction() {}
        """
        checks = ["use server", "zod", "revalidatePath", "submitAction"]
        res = score_code_snippet(valid_code, checks)
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 1.0)
        self.assertEqual(len(res["missing"]), 0)

    def test_export_data(self):
        data = export_benchmark_data()
        self.assertIn("Next.js Agent Evals: Success Rate (pass@4)", data["title"])
        self.assertEqual(len(data["models"]), 5)
        self.assertGreaterEqual(len(data["tasks"]), 6)


if __name__ == "__main__":
    unittest.main()
