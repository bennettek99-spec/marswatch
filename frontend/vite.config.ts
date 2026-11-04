import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// MW_STATIC=1 builds the offline snapshot bundle: relative paths and a classic (IIFE) script so that
// index.html works when opened directly from disk (file://), where ES-module scripts are blocked.
const isStatic = process.env.MW_STATIC === "1";

export default defineConfig({
  plugins: [react()],
  base: isStatic ? "./" : "/",
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/runs": "http://127.0.0.1:8000",
    },
  },
  build: {
    chunkSizeWarningLimit: 5000,
    outDir: isStatic ? "dist-static" : "dist",
    ...(isStatic ? { modulePreload: false, rollupOptions: { output: { format: "iife", inlineDynamicImports: true } } } : {}),
  },
});
