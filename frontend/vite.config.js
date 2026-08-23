import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend on :8000, so the frontend
// and backend can run as two processes with no CORS fuss during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
