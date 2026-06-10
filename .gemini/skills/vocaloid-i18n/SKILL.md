---
name: vocaloid-i18n
description: Internationalization workflows using Babel and JS translation extraction. Use when adding translatable strings or updating Japanese/English locales.
---

# 🌐 Internationalization (I18n)

- **Python/Jinja:** Wrap strings in `_()`.
- **JavaScript:** Use `window._("...")`.
- **Extraction:**
  - Python/Jinja: `bun run i18n:extract`
  - JS: `bun run i18n:extract:js`
- **Compilation:** Run `bun run i18n:compile`.
