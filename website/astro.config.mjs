import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  build: { inlineStylesheets: "auto" },
  devToolbar: { enabled: false },
  vite: { build: { chunkSizeWarningLimit: 900 } },
});
