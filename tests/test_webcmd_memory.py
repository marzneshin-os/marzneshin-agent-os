"""Unit tests for WebCMD Browser Memory & Token Optimization Engine (scripts/lib/webcmd_memory.py)."""

import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib import webcmd_memory


SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Enterprise Portal Documentation</title>
    <style>
        body { font-family: sans-serif; background: #fafafa; margin: 0; }
        .nav-item { color: blue; padding: 10px; display: inline-block; }
        .cookie-banner { position: fixed; bottom: 0; background: yellow; }
        /* Hundreds of lines of CSS */
        .grid { display: flex; flex-direction: column; }
    </style>
    <script>
        // Large script bundle
        window.__INITIAL_STATE__ = { user: null, telemetry: true, trackers: [1,2,3,4,5] };
        function trackEvent(e) { console.log('tracking', e); }
    </script>
</head>
<body>
    <header>
        <div class="logo">Corp Portal</div>
        <nav>
            <a href="/home" class="nav-item">Home</a>
            <a href="/pricing" class="nav-item">Pricing</a>
            <a href="/docs/api" class="nav-item">API Docs</a>
            <a href="/login" class="nav-item" id="login-btn">Log In</a>
        </nav>
    </header>
    <main>
        <h1>Agentic OS API Reference v2</h1>
        <p>The Marzneshin Agent OS provides an event-sourced control plane for multi-agent workflows.</p>
        <div class="search-section">
            <input type="text" name="q" placeholder="Search documentation..." id="search-input" />
            <button type="submit" id="search-btn">Search</button>
        </div>
        <section class="endpoints">
            <h2>Authentication Endpoint</h2>
            <p>POST /v1/auth/token with your client credentials.</p>
            <button class="copy-btn" data-clipboard="curl https://api.example.com/v1/auth">Copy Snippet</button>
        </section>
        <section class="pricing-card">
            <h3>Enterprise Plan</h3>
            <p>Unlimited autonomous agent leases, cryptographic receipts, and 5-path killswitch.</p>
            <a href="/subscribe?plan=enterprise" class="cta-button" id="cta-sub">Subscribe Now</a>
        </section>
    </main>
    <footer>
        <p>Copyright 2026 Enterprise Corp. All rights reserved. Terms of service, privacy policy.</p>
        <script>var x = 123;</script>
    </footer>
</body>
</html>
"""


class TestWebCmdMemory(unittest.TestCase):
    def setUp(self):
        # Use isolated test directory for web memory state
        self.test_root = REPO / "state" / "test_webcmd_scratch"
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root, ignore_errors=True)
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.orig_store_dir = webcmd_memory.WEBCMD_STORE_DIR
        webcmd_memory.WEBCMD_STORE_DIR = self.test_root

    def tearDown(self):
        webcmd_memory.WEBCMD_STORE_DIR = self.orig_store_dir
        if self.test_root.exists():
            import shutil
            shutil.rmtree(self.test_root, ignore_errors=True)

    def test_compress_html_cuts_significant_tokens(self):
        result = webcmd_memory.compress_html(SAMPLE_HTML, url="https://docs.example.com/api")
        self.assertTrue(result.compressed_text)
        self.assertGreater(result.savings_ratio, 0.50)
        self.assertGreater(len(result.actions), 0)
        self.assertIn("Enterprise Plan", result.compressed_text)
        self.assertNotIn("window.__INITIAL_STATE__", result.compressed_text)
        self.assertNotIn("font-family: sans-serif", result.compressed_text)
        
        # Verify action items mapped
        labels = [a["label"] for a in result.actions]
        self.assertTrue(any("Search" in l for l in labels))
        self.assertTrue(any("Subscribe" in l for l in labels))

    def test_sitemap_learn_and_lookup(self):
        url = "https://docs.example.com/api"
        comp = webcmd_memory.compress_html(SAMPLE_HTML, url=url)
        webcmd_memory.learn_route(
            url=url,
            title="Enterprise Portal Documentation",
            compressed_result=comp,
            shortcuts={"search": "#search-input", "login": "#login-btn", "subscribe": "#cta-sub"}
        )

        sitemap = webcmd_memory.get_domain_sitemap("docs.example.com")
        self.assertIsNotNone(sitemap)
        self.assertIn("docs.example.com", sitemap["domain"])
        self.assertIn("/api", sitemap["routes"])
        self.assertEqual(sitemap["shortcuts"]["search"]["selector"], "#search-input")
        self.assertEqual(sitemap["shortcuts"]["subscribe"]["selector"], "#cta-sub")

    def test_structural_fingerprint_and_invalidation(self):
        url = "https://docs.example.com/api"
        comp1 = webcmd_memory.compress_html(SAMPLE_HTML, url=url)
        webcmd_memory.learn_route(url=url, title="Docs v1", compressed_result=comp1)

        # Freshness check with exact same HTML should be fresh
        is_fresh = webcmd_memory.verify_freshness(url, SAMPLE_HTML)
        self.assertTrue(is_fresh)

        # Drastically altered HTML should detect drift
        altered_html = "<html><body><h1>Maintenance Mode</h1><p>Down for maintenance</p></body></html>"
        is_fresh_altered = webcmd_memory.verify_freshness(url, altered_html)
        self.assertFalse(is_fresh_altered)

    def test_profile_isolation(self):
        webcmd_memory.save_profile_state("agent_coder", {"cookies": {"session": "coder_xyz"}, "space": "code_review"})
        webcmd_memory.save_profile_state("agent_reviewer", {"cookies": {"session": "reviewer_abc"}, "space": "security"})

        coder_state = webcmd_memory.get_profile_state("agent_coder")
        reviewer_state = webcmd_memory.get_profile_state("agent_reviewer")

        self.assertEqual(coder_state["cookies"]["session"], "coder_xyz")
        self.assertEqual(reviewer_state["cookies"]["session"], "reviewer_abc")
        self.assertNotEqual(coder_state["space"], reviewer_state["space"])

    def test_fail_closed_on_broken_html(self):
        broken_html = "<<<not valid <html <broken >>>>"
        result = webcmd_memory.compress_html(broken_html, url="https://example.com/broken")
        self.assertIsInstance(result.compressed_text, str)
        self.assertIsInstance(result.actions, list)


if __name__ == "__main__":
    unittest.main()
