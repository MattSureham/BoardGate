import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    coverage: {
      // Browser-only entry points are exercised through the three-engine
      // Playwright suite. Unit coverage remains strict for admission code.
      exclude: ["src/build-env.d.ts", "src/generated/**", "src/main.ts", "src/worker.ts"],
      include: ["src/**/*.ts"],
      provider: "v8",
      reporter: ["text", "json-summary"],
      thresholds: {
        branches: 85,
        functions: 90,
        lines: 90,
        statements: 90,
      },
    },
    environment: "node",
    include: ["tests/unit/**/*.test.ts"],
    passWithNoTests: false,
  },
});
