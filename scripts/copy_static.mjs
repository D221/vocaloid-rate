// Copy app/static -> public/static so Vercel's CDN serves /static/* directly
// (static files are served before the /(.*) rewrite, so the Python function is
// not invoked for assets). Source of truth stays app/static for local dev,
// Docker and PyInstaller; this copy only runs in the Vercel build.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = resolve(root, "app/static");
const out = resolve(root, "public/static");

if (!existsSync(src)) {
  console.error("copy_static: app/static not found");
  process.exit(1);
}
mkdirSync(dirname(out), { recursive: true });
cpSync(src, out, { recursive: true });
console.log("copy_static: copied app/static -> public/static");
