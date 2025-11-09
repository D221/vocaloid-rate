// THEME LOGIC
const THEME_KEY = "theme";
const THEMES = ["light", "dark", "night", "black"];

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

// TRANSLATION LOGIC
let translations = {};

window._ = function (key, ...args) {
  let translated = translations[key] || key;
  if (args.length > 0) {
    translated = translated.replace(/%s/g, () => args.shift());
  }
  return translated;
};

// PWA SERVICE WORKER REGISTRATION
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/static/sw.js", { scope: "/" })
      .catch((err) => {
        console.error("ServiceWorker registration failed: ", err);
      });
  });
}

// GLOBAL INITIALIZATION

document.addEventListener("DOMContentLoaded", async () => {
  // Initialize the visual theme on every page load.
  window.initializeTheme();

  // Fetch translations for the current language.
  const lang = document.documentElement.lang || "en";
  try {
    const response = await fetch(`/api/translations?lang=${lang}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    translations = await response.json();
  } catch (error) {
    // <-- THE FIX IS HERE: ADDED THE OPENING BRACE
    console.error("Could not fetch translations:", error);
  }

  // --- Language Switcher Logic ---
  const languageSwitcher = document.getElementById("language-switcher");
  if (languageSwitcher) {
    languageSwitcher.addEventListener("click", () => {
      const currentLang = document.documentElement.lang || "en";
      const newLang = currentLang === "ja" ? "en" : "ja";
      const url = new URL(window.location.href);
      url.searchParams.set("lang", newLang);
      window.location.href = url.toString();
    });
  }

  // --- Mobile Menu Logic ---
  const menuToggle = document.getElementById("menu-toggle");
  const navLinks = document.getElementById("nav-links");

  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      navLinks.classList.toggle("hidden");
    });

    document.body.addEventListener("click", () => {
      if (!navLinks.classList.contains("hidden")) {
        navLinks.classList.add("hidden");
      }
    });
  }
});
