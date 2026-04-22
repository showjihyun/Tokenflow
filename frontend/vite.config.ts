import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    exclude: ["e2e/**", "e2e-real/**", "node_modules/**", "dist/**"],
    deps: {
      optimizer: {
        web: { enabled: false },
      },
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/test/**", "src/**/*.css"],
      // Ratchet thresholds — raise as we add coverage. The gate's job today
      // is preventing regression below the current baseline; incremental
      // PRs should bump these numbers as they land new tests.
      thresholds: {
        lines: 25,
        functions: 20,
        branches: 20,
        statements: 25,
      },
    },
  },
});
