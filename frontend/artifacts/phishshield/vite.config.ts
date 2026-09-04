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

  // Same-origin proxy for the Python backend, shared by dev and preview so the
  // built app never needs a baked absolute host/port.
  const proxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";
  const proxy = {
    "/api": { target: proxyTarget, changeOrigin: true },
    "/feedback": { target: proxyTarget, changeOrigin: true },
    "/scan-email": { target: proxyTarget, changeOrigin: true },
    "/retrain": { target: proxyTarget, changeOrigin: true },
    "/health": { target: proxyTarget, changeOrigin: true },
    "/recent-scans": { target: proxyTarget, changeOrigin: true },
    "/report": { target: proxyTarget, changeOrigin: true },
    "/ws": { target: proxyTarget, ws: true, changeOrigin: true },
  };

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
      chunkSizeWarningLimit: 500,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules")) {
              if (id.includes("recharts") || id.includes("d3-")) return "charts";
              if (id.includes("framer-motion")) return "motion";
              if (id.includes("lucide-react")) return "icons";
              if (id.includes("react-dom")) return "vendor-react-dom";
              if (id.includes("react")) return "vendor-react";
            }
          },
        },
      },
    },
    server: {
      port: devPort > 0 ? devPort : 5173,
      host: "0.0.0.0",
      allowedHosts: true,
      proxy,
      fs: {
        strict: true,
        deny: ["**/.*"],
      },
    },
    preview: {
      port: 4173,
      host: "0.0.0.0",
      allowedHosts: true,
      proxy,
    },
  };
});
