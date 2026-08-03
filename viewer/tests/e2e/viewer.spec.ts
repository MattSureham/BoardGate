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

test("fails closed on an active SVG without exposing admitted evidence", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_ACTIVE_SVG_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);
  const remoteRequests: string[] = [];
  page.on("request", (request) => {
    if (/^(?:https?|wss?):/u.test(request.url())) {
      remoteRequests.push(request.url());
    }
  });

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);

  await expect(page.getByText("Review unavailable.")).toBeVisible();
  await expect(page.getByText("SVG_ACTIVE_ELEMENT_REJECTED")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validated review summary" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Validated preview" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Validated report" })).toHaveCount(0);
  await expect(page.locator(".review-status, .preview-canvas, .report-content")).toHaveCount(0);

  expect(remoteRequests).toEqual([]);
  expect(bundleDigests(bundle)).toEqual(before);
});

test("defensively rejects a worker result whose preview root is outside the SVG namespace", async ({
  page,
}) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);

  await page.addInitScript(() => {
    class NamespaceBypassWorker {
      #messageListeners: Array<(event: { data: unknown }) => void> = [];

      addEventListener(type: string, listener: (event: { data: unknown }) => void): void {
        if (type === "message") {
          this.#messageListeners.push(listener);
        }
      }

      postMessage(message: { requestId: string }): void {
        const projectId = "prj-0000000000000000";
        const profileSha256 = "0".repeat(64);
        const data = {
          kind: "boardgate.viewer.result",
          protocolVersion: "1.0",
          requestId: message.requestId,
          result: {
            ok: true,
            summary: {
              projectId,
              profileId: "profile",
              profileSha256,
              overallStatus: "READY_FOR_REVIEW",
              sourceCount: 0,
              layerCount: 0,
              drillCount: 0,
              slotCount: 0,
              placementCount: 0,
              bomItemCount: 0,
              ruleCount: 0,
              findingCount: 0,
              coverageGapCount: 0,
              riskModes: [],
              diagnostics: [],
              disclaimer: "test",
              layers: [],
              findings: [],
            },
            previewSvg:
              `<svg xmlns="urn:not-svg" data-project-id="${projectId}" ` +
              `data-profile-sha256="${profileSha256}"/>`,
            reportMarkdown: "",
          },
        };
        queueMicrotask(() => {
          for (const listener of this.#messageListeners) {
            listener({ data });
          }
        });
      }

      terminate(): void {}
    }

    Object.defineProperty(globalThis, "Worker", {
      configurable: true,
      value: NamespaceBypassWorker,
    });
  });

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);

  await expect(page.getByText("Review unavailable.")).toBeVisible();
  await expect(page.getByText("VIEWER_INTERNAL_ERROR")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Validated review summary" })).toHaveCount(0);
  await expect(page.locator(".preview-canvas, .report-content")).toHaveCount(0);
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

test("renders the validated preview with layer toggles and no geometry mutation", async ({
  page,
}) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_SPATIAL_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);

  const remoteRequests: string[] = [];
  page.on("request", (request) => {
    if (/^(?:https?|wss?):/u.test(request.url())) {
      remoteRequests.push(request.url());
    }
  });

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();

  const preview = page.locator(".preview-canvas svg.preview-svg");
  await expect(preview).toBeVisible();
  await expect(preview).toHaveAttribute("data-project-id", /^prj-[0-9a-f]{16}$/);

  const geometryBefore = await preview
    .locator("path")
    .evaluateAll((elements) => elements.map((element) => element.getAttribute("d")));

  const layerGroups = preview.locator('g[id^="pcb-layer-"]');
  const toggles = page.locator('.layer-toggles input[type="checkbox"]');
  await expect(toggles).toHaveCount(await layerGroups.count());

  const firstToggle = toggles.first();
  const groupId = await firstToggle.getAttribute("data-layer-group");
  expect(groupId).not.toBeNull();
  const group = preview.locator(`#${groupId as string}`);
  await expect(group).toBeVisible();
  await firstToggle.uncheck();
  await expect(group).toBeHidden();
  await firstToggle.check();
  await expect(group).toBeVisible();

  const geometryAfter = await preview
    .locator("path")
    .evaluateAll((elements) => elements.map((element) => element.getAttribute("d")));
  expect(geometryAfter).toEqual(geometryBefore);
  expect(remoteRequests).toEqual([]);
  expect(bundleDigests(bundle)).toEqual(before);
});

test("focuses spatial Finding markers and moves focus between Findings", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_SPATIAL_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();

  const buttons = page.locator(".finding-button");
  await expect(buttons).toHaveCount(2);

  const firstId = await buttons.nth(0).getAttribute("data-finding-id");
  const secondId = await buttons.nth(1).getAttribute("data-finding-id");
  expect(firstId).not.toBeNull();
  expect(secondId).not.toBeNull();

  const firstMarker = page.locator(
    `.preview-canvas #spatial-findings [data-finding-id="${firstId as string}"]`,
  );
  const secondMarker = page.locator(
    `.preview-canvas #spatial-findings [data-finding-id="${secondId as string}"]`,
  );

  await buttons.nth(0).click();
  await expect(firstMarker).toHaveClass(/finding-focus/u);
  await expect(buttons.nth(0)).toHaveAttribute("aria-pressed", "true");

  await buttons.nth(1).click();
  await expect(firstMarker).not.toHaveClass(/finding-focus/u);
  await expect(secondMarker).toHaveClass(/finding-focus/u);
  await expect(buttons.nth(1)).toHaveAttribute("aria-pressed", "true");
  await expect(buttons.nth(0)).toHaveAttribute("aria-pressed", "false");

  expect(bundleDigests(bundle)).toEqual(before);
});

test("focuses legend Findings for non-spatial results", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_LEGEND_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();
  await expect(page.locator(".review-status")).toHaveText("NOT_READY_FOR_FABRICATION");

  const button = page.locator(".finding-button", { hasText: "drill_file_present" });
  await expect(button).toHaveCount(1);
  const findingId = await button.getAttribute("data-finding-id");
  expect(findingId).not.toBeNull();

  const legendMarker = page.locator(
    `.preview-canvas #non-spatial-findings [data-finding-id="${findingId as string}"]`,
  );
  await button.click();
  await expect(legendMarker).toHaveClass(/finding-focus/u);
});

test("renders an empty Finding list for a clean review", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");

  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();

  await expect(page.locator(".preview-canvas svg.preview-svg")).toBeVisible();
  await expect(page.locator('.layer-toggles input[type="checkbox"]')).toHaveCount(3);
  await expect(page.locator(".finding-list")).toContainText("No findings recorded");
});

test("renders the validated report as inert structured text", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_SPATIAL_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);

  const remoteRequests: string[] = [];
  page.on("request", (request) => {
    if (/^(?:https?|wss?):/u.test(request.url())) {
      remoteRequests.push(request.url());
    }
  });
  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();

  const report = page.locator(".report-content");
  await expect(page.getByRole("heading", { name: "Validated report" })).toBeVisible();
  await expect(report.getByRole("heading", { name: "PCB Manufacturing Review" })).toBeVisible();
  await expect(report.getByRole("heading", { name: "Blockers" })).toBeVisible();
  await expect(report.locator("strong", { hasText: "READY_FOR_REVIEW" })).toHaveCount(1);
  await expect(report.getByText(/fnd-[0-9a-f]{16}/u).first()).toBeVisible();
  await expect(report.getByText(/boardgate-project-id/u)).toHaveCount(0);
  expect(
    await report
      .locator("script, img, iframe, object, embed, a, form, input, video, audio")
      .count(),
  ).toBe(0);

  expect(remoteRequests).toEqual([]);
  expect(bundleDigests(bundle)).toEqual(before);
});

test("synchronizes Finding selection between the report and the preview", async ({ page }) => {
  const bundle = requiredEnvironment("BOARDGATE_VIEWER_E2E_SPATIAL_BUNDLE");
  const html = requiredEnvironment("BOARDGATE_VIEWER_E2E_HTML");
  const before = bundleDigests(bundle);

  const remoteRequests: string[] = [];
  page.on("request", (request) => {
    if (/^(?:https?|wss?):/u.test(request.url())) {
      remoteRequests.push(request.url());
    }
  });
  await page.goto(pathToFileURL(html).href);
  await page.getByLabel("Choose BoardGate review directory").setInputFiles(bundle);
  await expect(page.getByText("Bundle validation complete.")).toBeVisible();

  const reportButtons = page.locator(".report-finding-button");
  const firstId = (await reportButtons.first().getAttribute("data-finding-id")) as string;
  expect(firstId).toMatch(/^fnd-[0-9a-f]{16}$/u);
  await expect(page.locator(`.report-finding-button[data-finding-id="${firstId}"]`)).toHaveCount(2);

  await reportButtons.first().click();
  const firstMarker = page.locator(`.preview-canvas [data-finding-id="${firstId}"]`);
  await expect(firstMarker).toHaveClass(/finding-focus/u);
  await expect(page.locator(`.finding-button[data-finding-id="${firstId}"]`)).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  for (const button of await page
    .locator(`.report-finding-button[data-finding-id="${firstId}"]`)
    .all()) {
    await expect(button).toHaveAttribute("aria-pressed", "true");
  }

  const secondId = (await page
    .locator(".finding-button")
    .nth(1)
    .getAttribute("data-finding-id")) as string;
  await page.locator(".finding-button").nth(1).click();
  await expect(page.locator(`.preview-canvas [data-finding-id="${secondId}"]`)).toHaveClass(
    /finding-focus/u,
  );
  await expect(firstMarker).not.toHaveClass(/finding-focus/u);
  await expect(
    page.locator(`.report-finding-button[data-finding-id="${firstId}"]`).first(),
  ).toHaveAttribute("aria-pressed", "false");
  for (const button of await page
    .locator(`.report-finding-button[data-finding-id="${secondId}"]`)
    .all()) {
    await expect(button).toHaveAttribute("aria-pressed", "true");
  }

  expect(remoteRequests).toEqual([]);
  expect(bundleDigests(bundle)).toEqual(before);
});
