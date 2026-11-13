import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Every Frappe site uses the same cookie names (sid, user_id …) and browsers share cookies across ports, so the Baogee
// app runs on its own hostname: baogee.localhost (browsers resolve *.localhost by themselves, no /etc/hosts line
// needed). Its login never touches the other sites on this bench. Plain localhost redirects there.
const PORT = 5182;
const HOST = "baogee.localhost";
const SITE = "baogee";

function ownHostname(): Plugin {
  return {
    name: "baogee-own-hostname",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const requested = (req.headers.host ?? "").split(":")[0];
        if (requested === "localhost" || requested === "127.0.0.1") {
          res.writeHead(302, { Location: `http://${HOST}:${PORT}${req.url ?? "/"}` });
          res.end();
          return;
        }
        next();
      });
    },
  };
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_PROXY_TARGET || "http://127.0.0.1:8009";
  const proxy = {
    target,
    changeOrigin: true,
    headers: { Host: SITE, "X-Frappe-Site-Name": SITE },
    cookieDomainRewrite: "",
    secure: false,
  };
  return {
    // production: built into baogee_textile/public/frontend, served by Frappe from /assets/…; dev server: from /
    base: command === "build" ? "/assets/baogee_textile/frontend/" : "/",
    plugins: [react(), ownHostname()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: {
      port: PORT,
      strictPort: true,
      host: true,
      allowedHosts: [HOST, "localhost"],
      proxy: {
        "/api": proxy,
        "/files": proxy,
        "/private": proxy,
        "/assets": proxy,
        // Desk form and print view, opened from the React forms' Actions menu (same session cookie).
        "/app": proxy,
        "/desk": proxy,
        "/printview": proxy,
        // Biometric Sync console's gate display (iframe)
        "/checkin-display": proxy,
        "/biometric": proxy,
        "/socket.io": { target: env.VITE_SOCKETIO_TARGET || "http://127.0.0.1:9000", ws: true, changeOrigin: false,
          headers: { "X-Frappe-Site-Name": SITE } },
      },
    },
    build: {
      outDir: "../baogee_textile/public/frontend",
      emptyOutDir: true,
      sourcemap: false,
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          manualChunks: {
            "vendor-react": ["react", "react-dom", "react-router-dom"],
            "vendor-frappe": ["frappe-react-sdk", "swr", "axios"],
            "vendor-charts": ["recharts"],
          },
        },
      },
    },
  };
});
