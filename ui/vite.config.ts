import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8082",
        changeOrigin: true,
      },
    },
  },
  test: {
    // Тесты интерфейса: дизайн-примитивы, целостность локализации, схема.
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
