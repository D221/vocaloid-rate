---
name: vocaloid-frontend
description: Frontend UI development with Jinja2, Tailwind CSS, and vanilla JS
---

# 🎨 Frontend & UI

- **Style Guide:** Adhere to the baseline in `STYLEGUIDE.md` for color palette, button standards, component styling, and theming.
- **Source Files:** Edit `app/static/js/*.js` and `app/static/css/input.css`.
- **Contracts:** Maintain `data-*` attribute contracts in templates — JS relies on them heavily.
- **Theming:** Test changes against Light, Dark, Night, and Black themes. Use OKLCH variables (`var(--color-*)`) or Tailwind classes — never hardcode hex/RGB.
- **Color System:**
  - **Cyan** — Primary actions, navigation
  - **Amber** — Special/edit actions
  - **Sky** — Navigation/utility
  - **Green** — Positive/create states
  - **Red** — Danger/delete
  - **Purple** — Alternative filters
  - **Gray** — Neutral/secondary

## ⚡ Asset Compilation

Whenever you modify CSS or JS, run the build:

```bash
bun run build          # full build (CSS + JS + i18n)
bun run build:css      # CSS only
bun run build:js       # JS only (minifies via terser)
```

Verify the build succeeded before finishing.
