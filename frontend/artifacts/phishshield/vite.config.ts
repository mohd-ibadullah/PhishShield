import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const basePath = process.env.BASE_PATH || "/";

// §4.2: PORT is only used for the dev server. vite build never reads it.
const devPort = Number(process.env.VITE_DEV_PORT || process.env.PORT || "5173");

export default defineConfig(async () => {
  const plugins = [react(), tailwindcss()];

  if (process.env.ENABLE_RUNTIME_ERROR_OVERLAY === "true") {
    const { default: runtimeErrorOverlay } = await import(
      "@replit/vite-plugin-runtime-error-modal"
    );
    plugins.push(runtimeErrorOverlay());
  }

  return {
    base: basePath,
    plugins,
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "src"),
        "@assets": path.resolve(import.meta.dirname, "..", "..", "attached_assets"),
      },
      dedupe: ["react", "react-dom"],
    },
    root: path.resolve(import.meta.dirname),
    build: {
      outDir: path.resolve(import.meta.dirname, "dist/public"),
      emptyOutDir: true,
      chunkSizeWarningLimit: 1200,
    },
    server: {
      port: devPort > 0 ? devPort : 5173,
      host: "0.0.0.0",
      allowedHosts: true,
      proxy: {
        "/api": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/feedback": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/scan-email": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/retrain": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/health": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/recent-scans": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          changeOrigin: true,
        },
        "/ws": {
          target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
          ws: true,
          changeOrigin: true,
        },
      },
      fs: {
        strict: true,
        deny: ["**/.*"],
      },
    },
    preview: {
      port: 4173,
      host: "0.0.0.0",
      allowedHosts: true,
    },
  };
});
