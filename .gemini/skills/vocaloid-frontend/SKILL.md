---
name: vocaloid-frontend
description: Frontend UI development with Jinja2, Tailwind CSS, and vanilla JS. Use when changing templates, editing CSS/JS assets, or improving UI visibility.
---

# 🎨 Frontend & UI

- **Style Guide:** Adhere to the baseline in [STYLEGUIDE.md](../../../STYLEGUIDE.md) and the specialized [styleguide.md](references/styleguide.md) reference.
- **Source Files:** Edit `app/static/js/*.js` and `app/static/css/input.css`.
- **Contracts:** Maintain `data-*` attribute contracts in templates.
- **HTMX:** Use htmx for dynamic partial updates from `app/templates/partials/`.

## ⚡ Automatic Workflow: Asset Compilation

Whenever you modify a CSS or JS file, you MUST run the build process:

1. Apply the code change.
2. Run `bun run build` (or `build:css`/`build:js`) to update minified assets.
3. Verify the build succeeded before finishing.
