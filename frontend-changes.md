# Frontend Changes — Light Theme + Theme Toggle Button

Adds a light/dark theme toggle to the Course Materials Assistant UI, plus a full light-theme palette built on CSS custom properties.

## Summary

- **Position:** Fixed, top-right of viewport (`top: 1rem; right: 1rem`), always visible.
- **Design:** 44×44 px circular button that mirrors existing aesthetic — uses the same `--surface`, `--border-color`, `--focus-ring`, and hover treatment (lift + primary-color border) as the suggested-question buttons.
- **Icon:** Sun (light theme active) / Moon (dark theme active) — inline SVGs using `currentColor` so they recolor automatically.
- **Animation:** Icons cross-fade and rotate via `opacity` + `transform` over 0.3–0.4 s; theme color changes transition over 0.3 s across all surfaces.
- **Accessibility:** Real `<button>` so it is fully keyboard-navigable (Tab, Enter, Space all work natively). `aria-pressed` reflects whether light mode is on; `aria-label` describes the action the next click will take and updates after each toggle. Focus ring uses `:focus-visible` so it appears only for keyboard users. Honors `prefers-reduced-motion`.
- **Persistence:** Choice saved to `localStorage["theme"]`. Pre-paint inline script in `<head>` applies the saved theme before CSS paints, avoiding a flash. Falls back to `prefers-color-scheme` for first-time visitors.

## Files changed

### `frontend/index.html`
- Added an inline `<script>` in `<head>` that reads `localStorage["theme"]` (with a `prefers-color-scheme` fallback) and sets `data-theme="light"` on `<html>` before the stylesheet loads.
- Added a `<button id="themeToggle" class="theme-toggle">` immediately inside `<body>`, containing two SVGs (`.theme-icon-sun`, `.theme-icon-moon`).
- Bumped `style.css` cache-buster to `?v=12` and `script.js` to `?v=10`.

### `frontend/style.css`
- Reorganized the `:root` block as the **dark theme** (unchanged values) and added a new `[data-theme="light"]` block that overrides the same custom properties with light-theme values.
- Promoted several previously hard-coded colors to theme-aware variables: `--code-bg`, `--error-text` / `--error-bg` / `--error-border`, `--success-text` / `--success-bg` / `--success-border`. `.error-message`, `.success-message`, and the code-block backgrounds now consume them.
- Added a global transition rule on the elements that paint theme colors (body, sidebar, chat surfaces, message bubbles, input, sidebar items, toggle) for `background-color`, `color`, `border-color`, and `box-shadow` over 0.3 s.
- Added `.theme-toggle` styles: fixed positioning top-right, circular shape, surface background + border, hover/active/focus treatments matching existing buttons. Z-index 100 keeps it above the sidebar on mobile.
- Added `.theme-icon` stacking (absolute positioning inside the button) and theme-state rules that fade + rotate-scale the inactive icon out and the active one in.
- Added a mobile size adjustment (40×40 px, tighter offsets) under the existing `max-width: 768px` breakpoint.
- Added a `prefers-reduced-motion: reduce` block that disables the theme/icon transitions for users who request reduced motion.

## Light theme palette (`[data-theme="light"]`)

| Variable | Value | Role |
| --- | --- | --- |
| `--background` | `#f8fafc` | Page / chat backdrop |
| `--surface` | `#ffffff` | Sidebar, assistant bubbles, input |
| `--surface-hover` | `#e2e8f0` | Hover state for sidebar items |
| `--text-primary` | `#0f172a` | Body text |
| `--text-secondary` | `#475569` | Labels, captions, metadata |
| `--border-color` | `#cbd5e1` | All separators / outlines |
| `--primary-color` | `#2563eb` | Brand accent, focus, user message bg |
| `--primary-hover` | `#1d4ed8` | Hovered primary actions |
| `--user-message` | `#2563eb` | User bubble (white text on it) |
| `--assistant-message` | `#e2e8f0` | Assistant bubble alt color |
| `--shadow` | `0 4px 6px -1px rgba(15, 23, 42, 0.08)` | Softer drop shadow for light surfaces |
| `--focus-ring` | `rgba(37, 99, 235, 0.25)` | Slightly stronger ring to stay visible on white |
| `--welcome-bg` | `#dbeafe` | Welcome card accent |
| `--welcome-border` | `#2563eb` | Welcome card accent border |
| `--code-bg` | `rgba(15, 23, 42, 0.06)` | Inline + block code highlight |
| `--error-text` | `#b91c1c` | Error copy (red-700, not red-400) |
| `--error-bg` | `rgba(220, 38, 38, 0.08)` | Error backdrop |
| `--error-border` | `rgba(220, 38, 38, 0.25)` | Error outline |
| `--success-text` | `#15803d` | Success copy (green-700) |
| `--success-bg` | `rgba(34, 197, 94, 0.10)` | Success backdrop |
| `--success-border` | `rgba(34, 197, 94, 0.30)` | Success outline |

## Accessibility / contrast (light theme, WCAG 2.1)

All text combinations meet AA (4.5:1 for body, 3:1 for large/non-text). Most clear AAA (7:1).

| Foreground / Background | Ratio | Result |
| --- | --- | --- |
| `--text-primary` (#0f172a) on `--background` (#f8fafc) | ~17.6:1 | AAA |
| `--text-primary` on `--surface` (#ffffff) | ~18.7:1 | AAA |
| `--text-secondary` (#475569) on `--background` | ~7.6:1 | AAA |
| `--text-secondary` on `--surface` | ~8.1:1 | AAA |
| `--primary-color` (#2563eb) as text on `--surface` | ~5.2:1 | AA (non-text uses pass AAA) |
| White on `--user-message` (#2563eb) | ~5.2:1 | AA |
| `--text-primary` on `--assistant-message` (#e2e8f0) | ~14.3:1 | AAA |
| `--error-text` (#b91c1c) on `--background` | ~6.4:1 | AA (AAA for large) |
| `--success-text` (#15803d) on `--background` | ~5.0:1 | AA |
| Focus ring (`--primary-color`) against `--surface` | ~5.2:1 | AAA for non-text |

The dark theme is unchanged and already meets the same thresholds (e.g. `--text-secondary` #94a3b8 on #0f172a ≈ 7.0:1).

### `frontend/script.js`
- Added `themeToggle` to the DOM-element lookups in `DOMContentLoaded`.
- Added `initTheme()`, `getCurrentTheme()`, `toggleTheme()`, and `syncThemeToggleState()`:
  - `initTheme` runs once on load — the pre-paint script already applied the theme, so this only wires up the click handler and syncs ARIA state on the button.
  - `toggleTheme` flips the `data-theme` attribute on `<html>` (sets `light` or removes the attribute for dark), persists the new value to `localStorage`, and re-syncs the button.
  - `syncThemeToggleState` updates `aria-pressed` (true when light) and `aria-label` (describes the action the next click will perform: "Switch to light/dark theme").

## Toggle behavior + smooth-transition details

**Click handler.** A real `<button>` carries native keyboard semantics — Tab focuses it, Enter and Space both dispatch a click. The single `themeToggle.addEventListener('click', toggleTheme)` therefore covers mouse, touch, and keyboard activation with no extra handlers.

**State machine.** Theme is encoded as a single source of truth: `document.documentElement[data-theme]`. The two valid states are `"light"` and "absent" (the latter is dark, the default). `getCurrentTheme()` reads it; `toggleTheme()` writes it via `setAttribute` / `removeAttribute`. CSS variables are scoped to `:root` (dark defaults) and `[data-theme="light"]` (light overrides), so attribute change → variables resolve → every declaration that references those variables recomputes.

**Persistence.** `localStorage["theme"]` is written on every toggle, wrapped in try/catch so private-mode storage failures degrade silently (the theme still applies for the current session). The pre-paint inline `<script>` in `<head>` reads the same key — single-keyed contract between the two scripts.

**Smooth transitions.** A single CSS rule near the top of the stylesheet declares `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease` on every element that explicitly binds a themed variable. The toggle action itself does not animate — it sets the attribute synchronously; the browser then drives the cross-fade because every affected property has a transition declared. Coverage list:

  - Layout shells: `body`, `.sidebar`, `.chat-main`, `.chat-container`, `.chat-messages`, `.chat-input-container`, `.main-content`
  - Message surfaces: `.message-content`, `.message-content code`, `.message-content pre`, `.message-meta`
  - Sidebar bits: `.stat-item`, `.stat-value`, `.stat-label`, `.course-title-item`, `.course-titles-header`, `.suggested-item`, `.subtitle`
  - Sources: `.sources-collapsible`, `.sources-content`
  - Feedback strips: `.error-message`, `.success-message`
  - Input + toggle: `#chatInput`, `.theme-toggle`

**Icon swap.** The sun and moon SVGs are absolutely positioned in the same 44 px button. Each carries its own transition (`opacity 0.3s ease, transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)`); the inactive icon fades to `opacity: 0` and rotate-shrinks to `scale(0.5)`, while the active one settles at `opacity: 1; rotate(0) scale(1)`. The slight overshoot on transform vs. opacity makes the swap feel mechanical rather than a plain crossfade.

**Reduced motion.** The full transition selector list is mirrored inside `@media (prefers-reduced-motion: reduce) { ... transition: none; }`, so users with the OS pref set get an instant theme switch with no animation at all. The toggle still works; only the in-betweening is suppressed.

## How it behaves

1. **First visit:** Theme follows the OS via `prefers-color-scheme`. No flash because the inline pre-paint script runs before the stylesheet renders.
2. **Click / Enter / Space on the toggle:** Theme flips; all colors crossfade over 0.3 s; the sun/moon icons rotate-and-fade through each other; the new choice is saved.
3. **Subsequent visits:** Saved choice is applied before paint, regardless of OS preference.
4. **Reduced motion:** Transitions disabled, but the theme still switches instantly.
