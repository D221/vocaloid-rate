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
const TRANSLATIONS_CACHE_PREFIX = "jsTranslations:";

window._ = function (key, ...args) {
  let translated = translations[key] || key;
  if (args.length > 0) {
    translated = translated.replace(/%s/g, () => args.shift());
  }
  return translated;
};

window.showToast = function (message, type = "success") {
  const toast = document.createElement("div");
  const bgColor = type === "error" ? "bg-red-text" : "bg-green-text";
  toast.className = `fixed bottom-24 right-5 z-[2000] rounded-md px-4 py-3 font-semibold text-white shadow-lg ${bgColor}`;
  toast.textContent = window._(message);
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = "opacity 0.5s ease";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 500);
  }, 2500);
};

// PWA SERVICE WORKER REGISTRATION
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((err) => {
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
  const cacheKey = `${TRANSLATIONS_CACHE_PREFIX}${lang}`;
  try {
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      translations = JSON.parse(cached);
    } else {
      const response = await fetch(
        `/api/translations?lang=${encodeURIComponent(lang)}`,
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      translations = await response.json();
      sessionStorage.setItem(cacheKey, JSON.stringify(translations));
    }
  } catch (error) {
    console.error("Could not fetch translations:", error);
    translations = {};
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
    const closeMobileMenu = () => {
      navLinks.classList.add("hidden");
      navLinks.classList.remove("flex");
      menuToggle.setAttribute("aria-expanded", "false");
    };

    const openMobileMenu = () => {
      navLinks.classList.remove("hidden");
      navLinks.classList.add("flex");
      menuToggle.setAttribute("aria-expanded", "true");
    };

    menuToggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = !navLinks.classList.contains("hidden");
      if (isOpen) {
        closeMobileMenu();
      } else {
        openMobileMenu();
      }
    });

    navLinks.addEventListener("click", (e) => {
      if (
        e.target === navLinks ||
        e.target.closest("[data-mobile-menu-close]") ||
        e.target.closest("a")
      ) {
        closeMobileMenu();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !navLinks.classList.contains("hidden")) {
        closeMobileMenu();
      }
    });
  }
});
