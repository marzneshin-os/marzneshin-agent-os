# Impeccable — Reference Guide

## Anti-Slop Rules Catalog

These patterns are prohibited — they are the hallmarks of lazy AI-generated design:

| Slop Pattern | Why It Fails | Professional Remedy |
|--------------|-------------|---------------------|
| Default Inter font for everything | Looks generic and unbranded | Select font pairing matching product tone |
| Purple-to-blue gradient everywhere | Overused II design stereotype | Curate intentional, brand-aligned color system |
| Cards inside cards inside cards | Creates visual noise and heavy borders | Flatten hierarchy, use whitespace for grouping |
| Low-contrast gray text (`#999` on white) | Violates WCAG accessibility | Ensure minimum 4.5:1 contrast ratio |
| 2x3 icon tile grid for features | Cliché template filler | Content-driven layout with contextual visuals |
| Uniform `border-radius: 8px` on all elements | Monotonous shape language | Establish purposeful elevation and radius tiers |
| Default `box-shadow: 0 2px 4px rgba(0,0,0,0.1)` | Flat and muddy shadow | Layered, diffuse shadows with color tints |
| Rainbow gradient text | Distracting, illegible | Use accent color purposefully for emphasis |

## Color System Principles

1. **HSL Space:** Construct palettes in HSL for predictable luminance and saturation steps.
2. **Semantic Tokens:** Define tokens for background, surface, border, primary, accent, success, and error.
3. **Dark Mode Harmony:** Do not invert pure white (`#fff`) to pure black (`#000`). Use deep slate or navy neutrals (`hsl(220, 15%, 10%)`).
4. **Restraint:** Keep active interfaces to 3-5 core hues.

## Typography Scale

- **Scale Ratios:** Major Second (1.125), Minor Third (1.200), Major Third (1.250).
- **Body Text:** Minimum 16px font size with 1.5 - 1.7 line height.
- **Headings:** Tighten line height to 1.15 - 1.25 as font size increases.
- **Measure:** Constrain reading width to 45 - 75 characters (`ch`).

## Motion & Micro-Interactions

- Always use tailored cubic-bezier timing curves (e.g. `cubic-bezier(0.16, 1, 0.3, 1)` for springy ease-out).
- Default to fast durations: 150ms for state changes, 250-350ms for modal entrances.
- Always include @media (prefers-reduced-motion: reduce) fallbacks.
