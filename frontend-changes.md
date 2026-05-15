# Changes — Testing Framework for the RAG System

> Note: this work is backend test infrastructure (no frontend changes were
> made). The summary is written here per the `/implement-feature` slash
> command's instructions.

## What changed

Added test infrastructure for the FastAPI HTTP layer in `backend/tests/`,
configured pytest in `pyproject.toml`, and added the dev-only test
dependencies.

### Files added

- `backend/tests/__init__.py` — empty marker so the directory is importable.
- `backend/tests/conftest.py` — shared pytest fixtures (see below).
- `backend/tests/test_api.py` — endpoint tests for `/api/query`,
  `/api/courses`, and `/` (13 tests, all passing).

### Files modified

- `pyproject.toml`:
  - Added a `[dependency-groups] dev` group with `pytest>=8.3.0` and
    `httpx>=0.27.0` (httpx is required by `fastapi.testclient.TestClient`).
  - Added `[tool.pytest.ini_options]`:
    - `pythonpath = ["backend"]` — lets tests import `app`, `rag_system`,
      etc. as top-level modules (matches CLAUDE.md's described convention).
    - `testpaths = ["backend/tests"]` — pytest discovers from this root.
    - `addopts = "-ra --tb=short"` — concise failure output, show summary
      of all non-passing outcomes.
    - `filterwarnings` — suppress dependency-side deprecation noise so
      genuine test failures stand out.

## Fixtures provided by `conftest.py`

| Fixture | Purpose |
| --- | --- |
| `text_block(text)` | Factory for an Anthropic-shaped `text` content block. |
| `tool_use_block(id, name, input)` | Factory for an Anthropic-shaped `tool_use` content block. |
| `anthropic_message(content, stop_reason)` | Factory for a full `Message`-shaped object with `content`, `stop_reason`, and `usage`. Used by future `AIGenerator` tests. |
| `mock_vector_store` | `MagicMock` shaped like `VectorStore` with safe defaults (empty `SearchResults`, empty title list, count 0). Override per-test. |
| `sample_course_titles` / `sample_query_answer` / `sample_sources` | Canned values reused across endpoint tests. |
| `mock_rag_system` | `MagicMock` shaped like `RAGSystem`. `query()` returns `(answer, sources)`, `get_course_analytics()` returns the canned analytics dict, and `session_manager.create_session()` returns the deterministic id `"session_test_1"` so tests can assert on it. |
| `test_app` | A `FastAPI` app that mirrors `backend/app.py` but **skips the static-file mount and document ingestion** (both require paths that don't exist under pytest). Routes are wired against `mock_rag_system`. |
| `client` | `TestClient(test_app)`. |

### Why a separate test app

`backend/app.py` does two things at import/startup time that break test
collection:

1. Mounts `../frontend` as static files (path resolved from the launch dir,
   not the test working dir).
2. Ingests `../docs` in an `@app.on_event("startup")` handler.

Rather than monkey-patch around both, the `test_app` fixture rebuilds the
same routes inline using the same Pydantic request/response models. The
models are defined at module scope in `conftest.py` — defining them inside
the fixture closure caused FastAPI's type-hint resolution to misclassify
the body parameter as a query parameter (verified by reproducing the
`422 / loc:["query","request"]` failure).

## Endpoint tests (`test_api.py`)

Grouped into classes by endpoint:

### `TestQueryEndpoint` — `POST /api/query`
- Returns the expected `answer`, `sources`, and `session_id` shape.
- Auto-creates a session id when none is supplied and forwards it to
  `RAGSystem.query`.
- Reuses a caller-supplied `session_id` without creating a new one.
- A missing `query` field returns 422 (pydantic validation).
- A raised exception in `RAGSystem.query` surfaces as a 500 with the
  message in `detail` (matches the production handler).
- Empty `sources` serialize as `[]`, not `null`.

### `TestCoursesEndpoint` — `GET /api/courses`
- Returns `total_courses` and `course_titles` from analytics.
- Handles an empty catalog cleanly.
- Surfaces analytics exceptions as 500.

### `TestRootEndpoint` — `GET /`
- Returns a JSON status payload (the test app's stand-in for the static
  mount that production uses at `/`).

### `TestContentTypeAndShape`
- Parametrized check that all endpoints return `application/json`.

## How to run

```bash
uv sync --dev          # one-time, installs pytest + httpx
uv run pytest          # 13 passed in ~0.3s
uv run pytest backend/tests/test_api.py::TestQueryEndpoint
```

## Verification

```
backend\tests\test_api.py .............                                  [100%]
============================= 13 passed in 0.30s ==============================
```
---

# Frontend Changes — Code Quality Tooling

Adds essential code-quality tooling to the **frontend** (`frontend/*.html|css|js`) workflow,
without touching the Python backend.

## Scope

The original feature ask named `black` (a Python-only formatter). Because the task is
scoped to **front-end features only**, `black` does not apply — there is no Python in
`frontend/`. The frontend equivalent is **Prettier**, which formats HTML, CSS, and JS
under one tool, mirroring what `black` does for Python.

## New / modified files

### Added

| Path | Purpose |
| --- | --- |
| `.prettierrc.json` | Prettier config (4-space indent, single quotes, 100-col print width, LF line endings, `es5` trailing commas, JSON/YAML/MD overrides at 2-space). |
| `.prettierignore` | Excludes `backend/`, `node_modules/`, lockfiles, ChromaDB data, env files, and `frontend-changes.md` from formatting. |
| `package.json` | Declares `prettier ^3.3.3` as a dev dependency and exposes `npm run format`, `format:check`, `format:frontend`, `quality`. Marked `private: true` — never published. |
| `package-lock.json` | Auto-generated by `npm install` to pin the Prettier version. |
| `scripts/format.sh` | Bash helper: installs deps if missing, then runs `prettier --write` on the frontend. |
| `scripts/format-check.sh` | Bash helper: CI-style `prettier --check` on the frontend (non-zero exit on drift). |
| `scripts/quality.sh` | Bash entry point: runs all frontend quality checks (currently format-check). Extension point for future linters. |
| `scripts/format.ps1` | PowerShell parity of `format.sh` for Windows users. |
| `scripts/format-check.ps1` | PowerShell parity of `format-check.sh`. |
| `scripts/quality.ps1` | PowerShell parity of `quality.sh`. |

### Modified

| Path | Change |
| --- | --- |
| `.gitignore` | Appended `node_modules/` and npm debug log patterns so frontend tooling does not pollute the repo. |
| `frontend/index.html` | Reformatted by Prettier — consistent attribute wrapping, indentation, and trailing newlines. No semantic / DOM changes. |
| `frontend/script.js` | Reformatted by Prettier — removed trailing whitespace, normalized quote / spacing / semicolon style. No behavior changes. |
| `frontend/style.css` | Reformatted by Prettier — consistent rule spacing, one-declaration-per-line, multi-selector breakout (e.g. `0%, 80%, 100%` keyframe stops on separate lines). No visual changes. |

## Prettier configuration (`.prettierrc.json`)

```json
{
    "tabWidth": 4,
    "useTabs": false,
    "semi": true,
    "singleQuote": true,
    "printWidth": 100,
    "trailingComma": "es5",
    "arrowParens": "always",
    "endOfLine": "lf",
    "bracketSpacing": true,
    "htmlWhitespaceSensitivity": "css",
    "overrides": [
        { "files": "*.md", "options": { "tabWidth": 2, "proseWrap": "preserve" } },
        { "files": ["*.json", "*.yml", "*.yaml"], "options": { "tabWidth": 2 } }
    ]
}
```

Rationale for the non-defaults:

- **`tabWidth: 4`** matches the existing frontend indent; switching to 2 would have
  produced a large gratuitous diff with no readability win.
- **`singleQuote: true`** matches the JS already in `script.js`.
- **`printWidth: 100`** gives long HTML attributes (e.g. the suggested-question buttons)
  room without forcing them onto a single multi-line block.
- **`endOfLine: "lf"`** keeps line endings stable across Windows/macOS/Linux
  contributors and CI.
- **Override for `*.md` / `*.json` / `*.yml`** drops to 2-space indent — the universal
  convention for those formats.

## npm scripts (`package.json`)

| Script | What it does |
| --- | --- |
| `npm run format` | Rewrites every frontend file + top-level `*.md` / `*.json` in place. |
| `npm run format:frontend` | Same as above but only `frontend/**`. |
| `npm run format:check` | Reports drift without modifying files (exits 1 on drift). |
| `npm run quality` | Aggregates the quality gate. Currently delegates to `format:check`; new linters slot in here. |

## Standalone scripts (`scripts/`)

For contributors who prefer not to remember npm script names, or for CI / git hooks:

- **Bash:** `scripts/format.sh`, `scripts/format-check.sh`, `scripts/quality.sh`
- **PowerShell:** `scripts/format.ps1`, `scripts/format-check.ps1`, `scripts/quality.ps1`

Each script:

1. `cd`s to the repo root regardless of invocation directory.
2. Runs `npm install` automatically if `node_modules/` is missing (so a fresh clone
   works on the first invocation).
3. Invokes `npx prettier` with the appropriate mode.

## How a developer uses this

```bash
# One-time setup (or after pulling new deps):
npm install

# Format everything before committing:
npm run format
# …or, equivalently:
bash scripts/format.sh
# Windows:
pwsh scripts/format.ps1

# Verify formatting without writing (use in CI / pre-push):
npm run quality
# …or:
bash scripts/quality.sh
```

## Verification performed

1. `npx prettier --check "frontend/**/*.{js,css,html}"` → 3 files needed formatting.
2. `npx prettier --write "frontend/**/*.{js,css,html}"` → wrote all 3.
3. `npx prettier --check ...` again → **"All matched files use Prettier code style!"**
4. `bash scripts/format-check.sh` → exits 0 cleanly, confirms script wiring works.

## Out of scope (intentionally)

- **Python backend** (`backend/**`, `main.py`) — task is frontend-only. Adding `black`
  to the Python side is a separate change.
- **ESLint / Stylelint** — only formatting was requested. Linters can be added later
  under the `npm run quality` umbrella without breaking the existing wiring.
- **Pre-commit hooks** — not requested. The `scripts/quality.sh` entry point is the
  natural place to mount one (e.g. via `husky` or `pre-commit`) if desired.
---

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
