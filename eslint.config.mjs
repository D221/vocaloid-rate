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
    files: ["**/*.js"],
    languageOptions: {
      sourceType: "script",
    },
  },
]);
