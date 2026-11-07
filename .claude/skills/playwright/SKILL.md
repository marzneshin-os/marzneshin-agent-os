---
name: playwright
description: Browser automation, end-to-end testing, and visual UI verification using Playwright MCP (Khairallah Stack Tool #19). Use when inspecting web dashboards, taking page screenshots, clicking elements, or verifying frontend flows.
---

# Playwright Browser Automation

Playwright MCP empowers Claude Code to control a real browser, inspect running web consoles, capture screenshots, and conduct automated regression testing.

## Available Actions
- **Navigate**: Open URLs and local development servers (`http://localhost:3000`, dashboards).
- **Click & Type**: Select elements via CSS, text, or test-id (`click`, `fill`, `press`).
- **Screenshot**: Capture high-resolution visual evidence of UI rendering (`screenshot`).
- **Evaluate**: Execute in-browser JavaScript to inspect state, localStorage, and console logs.

## Best Practices
1. **Headless Execution**: Default to headless mode for speed; use viewport 1280x720 for consistent layout rendering.
2. **Visual Evidence**: Capture screenshots before and after significant DOM state transitions.
3. **Resilience**: Wait for element selectors explicitly instead of arbitrary sleeps.