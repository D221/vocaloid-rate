import js from "@eslint/js";
import globals from "globals";
import { defineConfig } from "eslint/config";

export default defineConfig([
  {
    files: ["**/*.{js,mjs,cjs}"],
    plugins: { js },
    extends: ["js/recommended"],
    languageOptions: {
      globals: {
        ...globals.browser,
        YT: "readonly",
        Chart: "readonly",
        Sortable: "readonly",
      },
    },
  },
  { files: ["**/*.js"], languageOptions: { sourceType: "script" } },
]);
