// app/static/js/theme.js

const THEME_KEY = "theme";
const THEMES = ["light", "dark", "night", "black"]; // Define available themes

window.getSystemTheme = function () {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

window.getStoredTheme = function () {
  return localStorage.getItem(THEME_KEY);
};

window.applyTheme = function (theme) {
  const doc = document.documentElement;
  doc.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
};

window.initializeTheme = function () {
  const storedTheme = window.getStoredTheme();
  const systemTheme = window.getSystemTheme();

  let initialTheme = systemTheme;
  if (storedTheme && THEMES.includes(storedTheme)) {
    initialTheme = storedTheme;
  }
  window.applyTheme(initialTheme);
};

window.cycleTheme = function () {
  const currentTheme = window.getStoredTheme() || window.getSystemTheme();
  const currentIndex = THEMES.indexOf(currentTheme);
  const nextIndex = (currentIndex + 1) % THEMES.length;
  const newTheme = THEMES[nextIndex];
  window.applyTheme(newTheme);
  return newTheme;
};

window.applyThemeImmediately = function () {
  const storedTheme = window.getStoredTheme();
  const systemTheme = window.getSystemTheme();

  let initialTheme = systemTheme;
  if (storedTheme && THEMES.includes(storedTheme)) {
    initialTheme = storedTheme;
  }
  document.documentElement.dataset.theme = initialTheme;
};
