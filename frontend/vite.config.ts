import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev server runs inside the `frontend` container on :5173.
// nginx fronts it on :80. HMR over the websocket comes through nginx.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Allow nginx (any Host header) to reach the dev server.
    cors: true,
    // HMR client connects to the host port nginx exposes.
    hmr: {
      protocol: "ws",
      host: "localhost",
      port: 80,
      clientPort: 80,
    },
  },
});
