# Official Reliance Weaving Mills branding and visual verification

The original supplied files were copied **byte-for-byte** into `frontend/public/assets/brand/` and `frontend/reference-brand-original/` (unchanged copies). The Vite build is not present in this checkpoint; after a successful build the public assets will be included in `frontend/dist/assets/brand/`. These verified identities must not be changed by the runtime CSS or generated assets:

| Asset | SHA-256 | Use |
|---|---|---|
| `RWML-Logo.svg` | `3c794f2c08e69a8fad7ed66e06478adb7e858690a5a8aefc80e1fe69c3474edf` | Light theme horizontal wordmark |
| `RWML-Logo-Dark.svg` | `446e129ae65ef4e67db65c65732faa0ef08927efe932d666e51d327f5345c6b3` | Dark theme horizontal wordmark |
| `RWML-Logo-Small.svg` | `7afccb252932cc80510cd2acefd88559334feb1b5574aae8038e8e3bb7d6858b` | Header emblem and SVG favicon |
| Original template `ui_design_template.html` | `5824cc712caa4e39cf6b5c6e6ec926783a4abf15eec3978029057d892336c6e1` | CSS/style reference only |

Theme tokens are centrally declared in `frontend/src/theme.css`, consumed by the Vite build after dependencies are installed. Important light tokens: `#008B42` brand green, `#f4f1eb` background, `#fcfbf8` surface, `#25231f` primary text, `#d9d3c8` border. Dark: `#1e2025` background, `#272a32` surface, `#f5f3ef` text, `#444956` border. Interface uses Newsreader, Plus Jakarta Sans and JetBrains Mono fallback families; no paid or external font files are bundled. User theme preference is client-only and applied before initial paint. The source SVGs are not recolored or stretched. Small logo lacks the viewBox; source remains unchanged, so small-size favicon quality must be checked in a real browser.

## Visual acceptance status

**Blocked by browser policy:** In this execution environment the browser denied localhost and file navigation with `ERR_BLOCKED_BY_ADMINISTRATOR` despite the API responding to direct HTTP requests. Therefore no actual 360/390/768/1366 viewport screenshots, color contrast scans, keyboard navigation audits, light/dark visual snapshots or 16/32/48px favicon inspection are claimed. The selected desktop/mobile components and built assets have only code/static/API smoke validation.

Before production use, open the real app in a supported browser and verify light/dark/system logo switching, screen-reader accessible names, labels/focus, table overflow, dialog sizing, source long-text wrapping, mobile nav, 200% zoom, reduced motion, live progress and validation errors. Do not use a brand-only HTML style guide screenshot as evidence that recruitment screens work.

## UI stack qualification note

The active source now uses React 19 with React Router, Vite, Tailwind 4 and strict TypeScript (real JSX/React definitions). The React 16 UMD fallback has been removed. **No npm lockfile, installed dependencies, build output, shadcn package verification or running UI exists in this checkpoint**: the registry operation failed `ENOTCACHED`. The backend safely returns `503 frontend_build_missing` rather than serving an outdated UI. Once Vite builds `frontend/dist`, the production FastAPI service serves it without a Node server. Native browser/accessibility verification is still open.
