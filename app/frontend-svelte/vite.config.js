import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const versionFile = path.resolve(__dirname, "../../VERSION");
const appVersion = fs.existsSync(versionFile)
  ? fs.readFileSync(versionFile, "utf8").trim()
  : "dev";

export default defineConfig({
  plugins: [svelte()],
  base: "",
  define: {
    "import.meta.env.VITE_APP_VERSION": JSON.stringify(appVersion || "dev"),
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
