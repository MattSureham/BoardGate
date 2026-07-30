import { defineConfig, devices } from "@playwright/test";

const localChromiumChannel =
  process.env.BOARDGATE_VIEWER_CHROMIUM_CHANNEL === "chrome" ? { channel: "chrome" as const } : {};

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: "list",
  timeout: 90_000,
  expect: {
    timeout: 65_000,
  },
  globalSetup: "./tests/e2e/global-setup.ts",
  use: {
    serviceWorkers: "block",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], ...localChromiumChannel },
    },
    {
      name: "firefox",
      use: { ...devices["Desktop Firefox"] },
    },
    {
      name: "webkit",
      use: { ...devices["Desktop Safari"] },
    },
  ],
});
