# Vocaloid Rate Style Guide

This document defines the baseline visual standards for the Vocaloid Rate project. Adhere to these patterns to ensure UI consistency across themes and deployment modes.

## 🎨 Color Palette (OKLCH)

The project uses a semantic color system that adapts to `light`, `dark`, `night`, and `black` themes. Always use the theme variables or Tailwind utility classes.

### Base Colors

| Name         | Description                                      |
| :----------- | :----------------------------------------------- |
| `background` | Primary page background.                         |
| `foreground` | Primary text color.                              |
| `card-bg`    | Background for cards, modals, and containers.    |
| `border`     | Standard border color for dividers and boxes.    |
| `header`     | High-contrast color for page titles and headers. |

### Semantic Action Colors

Each action color has a `text` variant (for borders/text) and a `hover` variant (for background hover states).

| Color      | Usage                                                                             |
| :--------- | :-------------------------------------------------------------------------------- |
| **Cyan**   | **Primary Actions:** Main navigation, "Rated Tracks", primary Login/Save buttons. |
| **Amber**  | **Special Actions:** Edit modes, "View Playlist", Guest login/register buttons.   |
| **Sky**    | **Navigation/Utility:** "Options", "Explore", "About", Import/Export functions.   |
| **Green**  | **Positive/New:** Create Playlist, Success states, Active toggles.                |
| **Red**    | **Danger/Alert:** Delete buttons, error messages, outdated database warnings.     |
| **Purple** | **Alternative:** Secondary filters or niche navigation items.                     |
| **Gray**   | **Neutral:** Secondary navigation, disabled states, meta-info.                    |

---

## 🔘 Button Standards

Most buttons follow a consistent "Outlined" or "Solid" pattern.

### 1. Standard Button

Used for navigation, filters, and primary actions.

- **Classes:** `rounded border border-[color]-text p-3 font-bold text-[color]-text shadow-md transition-colors hover:bg-[color]-hover`
- **Example:** `border-cyan-text text-cyan-text hover:bg-cyan-hover`

### 2. Small / Table Action Button

Used inside track tables or tight UI areas.

- **Classes:** `rounded border border-[color]-text px-2 py-1 text-sm font-semibold text-[color]-text hover:bg-[color]-hover`

---

## 📦 Components

### Cards & Containers

Standard containers for grouping content.

- **Classes:** `rounded border border-border bg-card-bg p-4 shadow-md`

### Form Inputs

Standard text/email/password inputs.

- **Classes:** `w-full rounded border border-border bg-background px-3 py-2 text-foreground shadow focus:border-[color]-text focus:outline-none`

### Pagination & Controls

- **Classes:** `cursor-pointer rounded border border-gray-text p-2 font-bold text-gray-text hover:bg-gray-hover disabled:opacity-50`

---

## 🌗 Themes

The project supports four themes via `data-theme` on the `<html>` tag:

1. **Light (Default):** Soft stone/white.
2. **Dark:** Deep stone.
3. **Night:** Navy/Indigo dark.
4. **Black:** Pure black for OLED.

**Implementation Note:** Always use the OKLCH variables (e.g., `var(--color-cyan-text)`) or Tailwind classes to ensure theme compatibility. Never hardcode hex codes or RGB values in component styles.
