---
name: impeccable
description: Frontend design director — eliminates AI slop aesthetics and builds production-grade, human-tier interfaces. Use when building UI, reviewing design, or when user invokes /impeccable. Provides design commands including craft, critique, polish, animate, typeset, and audit.
---

# Impeccable: Anti-Slop Frontend Design System

AI-generated interfaces often look repetitive: generic purple gradients, Inter font on everything, cards inside cards, lack of typographic hierarchy, and floating glassmorphism blobs. Impeccable enforces human-tier craftsmanship.

## The Anti-Slop Rules

1. **Typography with Character**:
   - Avoid defaulting to generic sans-serif. Choose deliberate fonts matching the domain (e.g. Plus Jakarta Sans, Outfit, Space Grotesk, IBM Plex Sans, JetBrains Mono for code).
   - Strict scale: `text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl`, `text-2xl`, `text-4xl`.

2. **Harmonious Color Palettes**:
   - Never use pure saturated RGB primaries (`#ff0000`, `#00ff00`, `#0000ff`).
   - Use curated HSL tokens with subtle contrast ratios (WCAG AAA compliant).
   - Deep rich neutrals (`#090d16`, `#0f172a`, `#182234`) rather than muddy grays.

3. **Restraint in Motion & Effects**:
   - Micro-interactions over loud animations: 150-250ms duration with `cubic-bezier(0.16, 1, 0.3, 1)`.
   - Borders should be subtle (`rgba(255, 255, 255, 0.08)` on dark, `rgba(0, 0, 0, 0.06)` on light).
   - Never nest cards within cards without clear functional elevation.

## Core Commands
- `/impeccable craft`: Generate a complete UI component following the design system tokens.
- `/impeccable critique`: Audit existing HTML/CSS/React code for visual slop and low-taste patterns.
- `/impeccable polish`: Refine spacing, typography, and micro-interactions of a page.
- `/impeccable typeset`: Establish typographic hierarchy, line-heights, and font pairings.
