import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Django runs on :8000 and serves API under /api/v1/...
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
      },
    },
  },
});
