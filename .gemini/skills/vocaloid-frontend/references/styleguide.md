# 🎨 Frontend Style Guide Reference

## Baseline Styling

Always adhere to the standards in the root `STYLEGUIDE.md`.

## Buttons & Interactive Elements

- **General Styling:** Use outlined buttons (`border-[color]-text text-[color]-text`) with `shadow-md`.
- **Transitions:** Always include `transition-colors duration-200 ease-in-out` for hover states.

## Color Usage

- **Primary (Cyan):** `cyan-text` / `cyan-hover`
- **Secondary (Amber):** `amber-text` / `amber-hover`
- **Info (Sky):** `sky-text` / `sky-hover`
- **Danger (Red):** `red-text` / `red-hover`

## Theming

- Test changes against both Light and Dark themes.
- Use `data-theme` aware variants in CSS (`@variant dark`, etc.).
