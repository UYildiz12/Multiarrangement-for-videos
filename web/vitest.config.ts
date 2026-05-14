import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    preserveSymlinks: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    css: false,
  },
});
