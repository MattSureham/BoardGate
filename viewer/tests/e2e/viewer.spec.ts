import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

import { expect, test } from "@playwright/test";

const EXPECTED_PATHS = [
  "findings.json",
  "logs/run.jsonl",
  "manifest.json",
  "preview.svg",
  "project.json",
  "report.md",
] as const;

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function logicalFiles(root: string, prefix = ""): string[] {
  return readdirSync(join(root, prefix), { withFileTypes: true })
    .flatMap((entry) => {
      const logicalPath = prefix.length === 0 ? entry.name : `${prefix}/${entry.name}`;
      return entry.isDirectory() ? logicalFiles(root, logicalPath) : [logicalPath];
    })
    .sort();
}

function bundleDigests(root: string): ReadonlyMap<string, string> {
  return new Map(
    logicalFiles(root).map((path) => [
      path,
      createHash("sha256")
        .update(readFileSync(join(root, path)))
        .digest("hex"),
    ]),
  );
}

test("admits a complete local bundle without network, storage, or writes", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);
  expect([...before.keys()]).toEqual(EXPECTED_PATHS);

  const remoteRequests: string[] = [];
  page.on("request", (request) => {
    if (/^(?:https?|wss?):/u.test(request.url())) {
      remoteRequests.push(request.url());
    }
  });
  await page.addInitScript(() => {
    const probe = {
      cache: 0,
      fetch: 0,
      indexedDb: 0,
      serviceWorker: 0,
      storageWrite: 0,
      webSocket: 0,
    };
    Object.defineProperty(globalThis, "__boardgateCapabilityProbe", {
      configurable: false,
      value: probe,
    });

    const originalFetch = globalThis.fetch;
    globalThis.fetch = ((...arguments_: Parameters<typeof fetch>) => {
      probe.fetch += 1;
      return originalFetch(...arguments_);
    }) as typeof fetch;

    const OriginalWebSocket = globalThis.WebSocket;
    Object.defineProperty(globalThis, "WebSocket", {
      configurable: true,
      value: class extends OriginalWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          probe.webSocket += 1;
          super(url, protocols);
        }
      },
    });

    for (const method of ["setItem", "removeItem", "clear"] as const) {
      const original = Storage.prototype[method];
      Object.defineProperty(Storage.prototype, method, {
        configurable: true,
        value: function storageMutation(this: Storage, ...arguments_: never[]): void {
          probe.storageWrite += 1;
          Reflect.apply(original, this, arguments_);
        },
      });
    }

    for (const method of ["open", "deleteDatabase"] as const) {
      const original = IDBFactory.prototype[method];
      Object.defineProperty(IDBFactory.prototype, method, {
        configurable: true,
        value: function indexedDbMutation(
          this: IDBFactory,
          ...arguments_: never[]
        ): IDBOpenDBRequest {
          probe.indexedDb += 1;
          return Reflect.apply(original, this, arguments_) as IDBOpenDBRequest;
        },
      });
    }

    if ("caches" in globalThis) {
      for (const method of ["open", "delete"] as const) {
        const original = CacheStorage.prototype[method];
        Object.defineProperty(CacheStorage.prototype, method, {
          configurable: true,
          value: function cacheMutation(
            this: CacheStorage,
            ...arguments_: never[]
          ): Promise<unknown> {
            probe.cache += 1;
            return Reflect.apply(original, this, arguments_) as Promise<unknown>;
          },
        });
      }
    }

    if ("serviceWorker" in navigator) {
      const original = ServiceWorkerContainer.prototype.register;
      Object.defineProperty(ServiceWorkerContainer.prototype, "register", {
        configurable: true,
        value: function serviceWorkerRegistration(
          this: ServiceWorkerContainer,
          ...arguments_: never[]
        ): Promise<ServiceWorkerRegistration> {
          probe.serviceWorker += 1;
          return Reflect.apply(original, this, arguments_) as Promise<ServiceWorkerRegistration>;
        },
      });
    }
  });

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);

  await expect(page.getByText("Bundle validation complete.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validated review summary" })).toBeVisible();
  await expect(page.locator(".review-status")).toHaveText("READY_FOR_REVIEW");
  await expect(page.locator(".summary-grid")).toContainText("default-prototype-2layer");
  await expect(page.locator(".review-summary")).toContainText(
    "BoardGate provides deterministic evidence for engineer review",
  );

  expect(remoteRequests).toEqual([]);
  expect(await page.evaluate(() => localStorage.length)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  expect(
    await page.evaluate(
      () =>
        (
          globalThis as typeof globalThis & {
            __boardgateCapabilityProbe: Record<string, number>;
          }
        ).__boardgateCapabilityProbe,
    ),
  ).toEqual({
    cache: 0,
    fetch: 0,
    indexedDb: 0,
    serviceWorker: 0,
    storageWrite: 0,
    webSocket: 0,
  });
  expect(logicalFiles(bundle)).toEqual(EXPECTED_PATHS);
  expect(bundleDigests(bundle)).toEqual(before);
});

test("clears admitted evidence before rejecting a replacement selection", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const invalidBundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_INVALID_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");

  await page.goto(pathToFileURL(html).href);
  const input = page.getByLabel("Choose BoardGate review directory");
  await input.setInputFiles(bundle);
  await expect(page.getByRole("heading", { name: "Validated review summary" })).toBeVisible();

  await input.setInputFiles(invalidBundle);

  await expect(page.getByText("Review unavailable.")).toBeVisible();
  await expect(page.getByText("ARTIFACT_INVENTORY_MISMATCH")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validated review summary" })).toHaveCount(0);
  await expect(page.locator(".review-status")).toHaveCount(0);
});

test("terminates and revokes an in-flight worker before validating a replacement", async ({
  page,
}) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const invalidBundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_INVALID_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");

  await page.addInitScript(() => {
    const cleanup = { posted: 0, revoked: 0, terminated: 0 };
    Object.defineProperty(globalThis, "__boardgateReplacementProbe", {
      configurable: false,
      value: cleanup,
    });

    class SilentWorker {
      addEventListener(): void {}

      postMessage(): void {
        cleanup.posted += 1;
      }

      terminate(): void {
        cleanup.terminated += 1;
      }
    }
    Object.defineProperty(globalThis, "Worker", {
      configurable: true,
      value: SilentWorker,
    });

    const originalRevoke = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url: string): void => {
      cleanup.revoked += 1;
      originalRevoke(url);
    };
  });

  await page.goto(pathToFileURL(html).href);
  const input = page.getByLabel("Choose BoardGate review directory");
  await input.setInputFiles(bundle);
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          (
            globalThis as typeof globalThis & {
              __boardgateReplacementProbe: { posted: number };
            }
          ).__boardgateReplacementProbe.posted,
      ),
    )
    .toBe(1);

  await input.setInputFiles(invalidBundle);

  await expect(page.getByText("Review unavailable.")).toBeVisible();
  await expect(page.getByText("ARTIFACT_INVENTORY_MISMATCH")).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        (
          globalThis as typeof globalThis & {
            __boardgateReplacementProbe: {
              posted: number;
              revoked: number;
              terminated: number;
            };
          }
        ).__boardgateReplacementProbe,
    ),
  ).toEqual({ posted: 1, revoked: 1, terminated: 1 });
});

test("terminates and revokes a worker that reaches its deadline", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");

  await page.addInitScript(() => {
    const cleanup = { revoked: 0, terminated: 0 };
    Object.defineProperty(globalThis, "__boardgateCleanupProbe", {
      configurable: false,
      value: cleanup,
    });

    const originalSetTimeout = globalThis.setTimeout;
    globalThis.setTimeout = ((handler: TimerHandler, timeout?: number, ...arguments_: unknown[]) =>
      originalSetTimeout(
        handler,
        timeout === 60_000 ? 25 : timeout,
        ...arguments_,
      )) as typeof globalThis.setTimeout;

    class SilentWorker {
      addEventListener(): void {}

      postMessage(): void {}

      terminate(): void {
        cleanup.terminated += 1;
      }
    }
    Object.defineProperty(globalThis, "Worker", {
      configurable: true,
      value: SilentWorker,
    });

    const originalRevoke = URL.revokeObjectURL.bind(URL);
    URL.revokeObjectURL = (url: string): void => {
      cleanup.revoked += 1;
      originalRevoke(url);
    };
  });

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);

  await expect(page.getByText("Review unavailable.")).toBeVisible();
  await expect(page.getByText("VIEWER_WORKER_TIMEOUT")).toBeVisible();
  await expect(page.locator(".review-summary")).toBeEmpty();
  expect(
    await page.evaluate(
      () =>
        (
          globalThis as typeof globalThis & {
            __boardgateCleanupProbe: {
              revoked: number;
              terminated: number;
            };
          }
        ).__boardgateCleanupProbe,
    ),
  ).toEqual({ revoked: 1, terminated: 1 });
});
