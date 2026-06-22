---
name: vocaloid-i18n
description: Internationalization with Babel and JS translation extraction
---

# 🌐 Internationalization (I18n)

- **Python/Jinja:** Wrap strings in `_()`.
- **JavaScript:** Use `window._("...")`.
- **Extraction:**
  - Python/Jinja + JS: `bun run i18n:extract`
  - JS only: `bun run i18n:extract:js`
- **Compilation:** Run `bun run i18n:compile`.
- **Supported locales:** `en` (default) and `ja`.
- Do not hand-edit generated `.mo` files or `locales/js_translations.json` directly.
