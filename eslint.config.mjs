import js from "@eslint/js";
import globals from "globals";
import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    ignores: ["docs/"],
  },
  {
    files: ["**/*.{js,mjs,cjs}"],
    ...js.configs.recommended,
    languageOptions: {
      globals: {
        ...globals.browser,
        YT: "readonly",
        Chart: "readonly",
        Sortable: "readonly",
      },
    },
  },
  {
    // This block ONLY applies to your Service Worker file
    files: ["app/static/sw.js"],
    languageOptions: {
      globals: {
        // 1. Import all standard Service Worker globals (like self, caches, importScripts)
        ...globals.serviceworker,

        // 2. Define the functions that are imported from idb-helper.js
        saveRequest: "readonly",
        getAllRequests: "readonly",
        clearRequests: "readonly",
        openSyncDB: "readonly", // Good practice to include this one too
      },
    },
  },
  {
    files: ["**/*.js"],
    languageOptions: {
      sourceType: "script",
    },
  },
]);
