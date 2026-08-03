import {
  type ReviewSummary,
  type ValidationResult,
  VIEWER_PROTOCOL_VERSION,
  type ViewerError,
  type ViewerFinding,
  type ViewerLayer,
  type ViewerWorkerResponse,
  type WorkerFile,
  type WorkerTransferFile,
} from "./contracts";
import { VIEWER_RESOURCE_POLICY } from "./policy";
import { type ReportInline, tokenizeReport } from "./report";
import { normalizeSelectedFiles, SelectionError } from "./selection";
import "./style.css";

const TIMEOUT_ERROR: ViewerError = Object.freeze({
  code: "VIEWER_WORKER_TIMEOUT",
  summary: "The viewer could not validate this bundle within its resource deadline.",
});
const INTERNAL_ERROR: ViewerError = Object.freeze({
  code: "VIEWER_INTERNAL_ERROR",
  summary: "The viewer could not validate this bundle without exposing partial results.",
});
const RESOURCE_ERROR: ViewerError = Object.freeze({
  code: "ARTIFACT_RESOURCE_LIMIT",
  summary: "The selected bundle exceeds the offline viewer resource policy.",
});
const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

interface ActiveWorker {
  readonly worker: Worker;
  readonly objectUrl: string;
  readonly requestId: string;
  readonly timeoutId: ReturnType<typeof setTimeout>;
}

export interface ViewerElements {
  readonly input: HTMLInputElement;
  readonly chooseButton: HTMLButtonElement;
  readonly status: HTMLElement;
  readonly summary: HTMLElement;
  readonly preview: HTMLElement;
  readonly report: HTMLElement;
  readonly error: HTMLElement;
}

type WorkerFactory = (source: string) => {
  readonly worker: Worker;
  readonly objectUrl: string;
};

function browserWorkerFactory(source: string): {
  readonly worker: Worker;
  readonly objectUrl: string;
} {
  const objectUrl = URL.createObjectURL(new Blob([source], { type: "text/javascript" }));
  try {
    return {
      worker: new Worker(objectUrl, { name: "boardgate-bundle-validator" }),
      objectUrl,
    };
  } catch (error) {
    URL.revokeObjectURL(objectUrl);
    throw error;
  }
}

function isWorkerResponse(value: unknown): value is ViewerWorkerResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Partial<ViewerWorkerResponse>;
  return (
    candidate.kind === "boardgate.viewer.result" &&
    candidate.protocolVersion === VIEWER_PROTOCOL_VERSION &&
    typeof candidate.requestId === "string" &&
    typeof candidate.result === "object" &&
    candidate.result !== null &&
    typeof (candidate.result as Partial<ValidationResult>).ok === "boolean"
  );
}

function appendDefinition(list: HTMLDListElement, label: string, value: string | number): void {
  const term = document.createElement("dt");
  term.textContent = label;
  const definition = document.createElement("dd");
  definition.textContent = String(value);
  list.append(term, definition);
}

export function renderSummary(container: HTMLElement, summary: ReviewSummary): void {
  container.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = "Validated review summary";

  const status = document.createElement("p");
  status.className = "review-status";
  status.dataset.status = summary.overallStatus;
  status.textContent = summary.overallStatus;

  const identity = document.createElement("dl");
  identity.className = "summary-grid";
  appendDefinition(identity, "Project ID", summary.projectId);
  appendDefinition(identity, "Profile", summary.profileId);
  appendDefinition(identity, "Profile SHA-256", summary.profileSha256);
  appendDefinition(identity, "Sources", summary.sourceCount);
  appendDefinition(identity, "Layers", summary.layerCount);
  appendDefinition(identity, "Round drills", summary.drillCount);
  appendDefinition(identity, "Routed slots", summary.slotCount);
  appendDefinition(identity, "Placements", summary.placementCount);
  appendDefinition(identity, "BOM rows", summary.bomItemCount);
  appendDefinition(identity, "Rules", summary.ruleCount);
  appendDefinition(identity, "Findings", summary.findingCount);
  appendDefinition(identity, "Coverage gaps", summary.coverageGapCount);

  const risksHeading = document.createElement("h3");
  risksHeading.textContent = "Risk modes";
  const risks = document.createElement("ul");
  risks.className = "plain-list";
  if (summary.riskModes.length === 0) {
    const item = document.createElement("li");
    item.textContent = "None recorded";
    risks.append(item);
  } else {
    for (const mode of summary.riskModes) {
      const item = document.createElement("li");
      item.textContent = mode;
      risks.append(item);
    }
  }

  container.append(heading, status, identity, risksHeading, risks);

  if (summary.overallStatus === "ANALYSIS_FAILED") {
    const diagnosticHeading = document.createElement("h3");
    diagnosticHeading.textContent = "Analysis diagnostics";
    const diagnostics = document.createElement("ul");
    diagnostics.className = "diagnostics";
    for (const diagnostic of summary.diagnostics) {
      const item = document.createElement("li");
      const code = document.createElement("code");
      code.textContent = diagnostic.code;
      item.append(code, document.createTextNode(` — ${diagnostic.summary}`));
      diagnostics.append(item);
    }
    container.append(diagnosticHeading, diagnostics);
  }

  const disclaimer = document.createElement("p");
  disclaimer.className = "disclaimer";
  disclaimer.textContent = summary.disclaimer;
  container.append(disclaimer);
}

function buildLayerToggles(canvas: HTMLElement, layers: readonly ViewerLayer[]): HTMLElement {
  const list = document.createElement("ul");
  list.className = "layer-toggles";
  for (const layer of layers) {
    const item = document.createElement("li");
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.dataset.layerGroup = layer.groupId;
    const text = document.createElement("span");
    text.textContent = `${layer.role} · ${layer.side} · ${layer.layerId}`;
    checkbox.addEventListener("change", () => {
      const group = canvas.querySelector<SVGElement>(`#${CSS.escape(layer.groupId)}`);
      if (group !== null) {
        group.style.visibility = checkbox.checked ? "visible" : "hidden";
      }
    });
    label.append(checkbox, text);
    item.append(label);
    list.append(item);
  }
  return list;
}

function buildFindingList(
  findings: readonly ViewerFinding[],
  onFindingSelect: (findingId: string) => void,
): HTMLElement {
  const list = document.createElement("ul");
  list.className = "finding-list";
  if (findings.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No findings recorded";
    list.append(item);
    return list;
  }
  for (const finding of findings) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "finding-button";
    button.dataset.findingId = finding.findingId;
    button.dataset.severity = finding.severity;
    button.setAttribute("aria-pressed", "false");
    const identifier = document.createElement("code");
    identifier.textContent = finding.findingId;
    const detail = document.createElement("span");
    detail.textContent = `${finding.title} — ${finding.ruleId} · ${finding.severity} · ${
      finding.spatial ? "spatial" : "legend"
    }`;
    button.append(identifier, detail);
    button.addEventListener("click", () => {
      onFindingSelect(finding.findingId);
    });
    item.append(button);
    list.append(item);
  }
  return list;
}

export function renderPreview(
  section: HTMLElement,
  previewSvg: string,
  summary: ReviewSummary,
  onFindingSelect: (findingId: string) => void,
): boolean {
  const parsed = new DOMParser().parseFromString(previewSvg, "image/svg+xml");
  const parsedRoot = parsed.documentElement;
  if (
    parsed.querySelector("parsererror") !== null ||
    parsedRoot.localName !== "svg" ||
    parsedRoot.namespaceURI !== SVG_NAMESPACE ||
    parsedRoot.getAttribute("data-project-id") !== summary.projectId
  ) {
    return false;
  }
  const svgElement = document.importNode(parsedRoot, true);
  svgElement.setAttribute("class", "preview-svg");

  const heading = document.createElement("h2");
  heading.textContent = "Validated preview";
  const layout = document.createElement("div");
  layout.className = "preview-layout";
  const canvas = document.createElement("div");
  canvas.className = "preview-canvas";
  canvas.append(svgElement);

  const panel = document.createElement("aside");
  panel.className = "preview-panel";
  const layersHeading = document.createElement("h3");
  layersHeading.textContent = "Layers";
  const findingsHeading = document.createElement("h3");
  findingsHeading.textContent = "Findings";
  panel.append(
    layersHeading,
    buildLayerToggles(canvas, summary.layers),
    findingsHeading,
    buildFindingList(summary.findings, onFindingSelect),
  );

  layout.append(canvas, panel);
  section.replaceChildren(heading, layout);
  return true;
}

function appendInline(parent: HTMLElement, inline: readonly ReportInline[]): void {
  for (const segment of inline) {
    if (segment.bold) {
      const strong = document.createElement("strong");
      strong.textContent = segment.text;
      parent.append(strong);
    } else {
      parent.append(document.createTextNode(segment.text));
    }
  }
}

const REPORT_FINDING_HEADING = /^fnd-[0-9a-f]{16}\b/u;

export function renderReport(
  section: HTMLElement,
  reportMarkdown: string,
  onFindingSelect: (findingId: string) => void,
): void {
  const heading = document.createElement("h2");
  heading.textContent = "Validated report";
  const content = document.createElement("div");
  content.className = "report-content";
  for (const block of tokenizeReport(reportMarkdown)) {
    if (block.kind === "heading") {
      const element = document.createElement(`h${Math.min(block.level + 1, 6)}`);
      const findingId = REPORT_FINDING_HEADING.exec(
        block.inline.map((segment) => segment.text).join(""),
      )?.[0];
      if (findingId === undefined) {
        appendInline(element, block.inline);
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "report-finding-button";
        button.dataset.findingId = findingId;
        button.setAttribute("aria-pressed", "false");
        appendInline(button, block.inline);
        button.addEventListener("click", () => {
          onFindingSelect(findingId);
        });
        element.append(button);
      }
      content.append(element);
    } else if (block.kind === "paragraph") {
      const element = document.createElement("p");
      appendInline(element, block.inline);
      content.append(element);
    } else {
      const element = document.createElement("ul");
      element.className = "report-list";
      for (const item of block.items) {
        const entry = document.createElement("li");
        entry.className = `report-item-depth-${item.depth}`;
        appendInline(entry, item.inline);
        element.append(entry);
      }
      content.append(element);
    }
  }
  section.replaceChildren(heading, content);
}

export class ViewerController {
  readonly #elements: ViewerElements;
  readonly #workerSource: string;
  readonly #workerFactory: WorkerFactory;
  #active: ActiveWorker | undefined;
  #requestSequence = 0;

  constructor(
    elements: ViewerElements,
    workerSource: string,
    workerFactory: WorkerFactory = browserWorkerFactory,
  ) {
    this.#elements = elements;
    this.#workerSource = workerSource;
    this.#workerFactory = workerFactory;
  }

  start(): void {
    this.#elements.chooseButton.addEventListener("click", () => {
      this.#elements.input.click();
    });
    this.#elements.input.addEventListener("change", () => {
      void this.load(this.#elements.input.files ?? []);
    });
    this.#setNeutral("No review bundle selected.");
  }

  dispose(): void {
    this.#cancelActive();
    this.#elements.summary.replaceChildren();
    this.#elements.preview.replaceChildren();
    this.#elements.preview.hidden = true;
    this.#elements.report.replaceChildren();
    this.#elements.report.hidden = true;
  }

  async load(files: Iterable<File>): Promise<void> {
    this.#cancelActive();
    this.#elements.summary.replaceChildren();
    this.#elements.preview.replaceChildren();
    this.#elements.preview.hidden = true;
    this.#elements.report.replaceChildren();
    this.#elements.report.hidden = true;
    this.#elements.error.replaceChildren();
    this.#elements.error.hidden = true;
    this.#elements.status.textContent = "Validating selected bundle…";
    this.#elements.status.dataset.state = "loading";

    let normalized: readonly WorkerFile[];
    try {
      normalized = normalizeSelectedFiles(files);
    } catch (error) {
      this.#showError(error instanceof SelectionError ? error.viewerError : INTERNAL_ERROR);
      return;
    }

    let created: ReturnType<WorkerFactory>;
    try {
      created = this.#workerFactory(this.#workerSource);
    } catch {
      this.#showError(INTERNAL_ERROR);
      return;
    }

    const requestId = `request-${++this.#requestSequence}`;
    const timeoutId = setTimeout(() => {
      if (this.#active?.requestId === requestId) {
        this.#finishActive();
        this.#showError(TIMEOUT_ERROR);
      }
    }, VIEWER_RESOURCE_POLICY.workerDeadlineMs);
    this.#active = {
      ...created,
      requestId,
      timeoutId,
    };

    created.worker.addEventListener("message", (event: MessageEvent<unknown>) => {
      if (
        this.#active?.requestId !== requestId ||
        !isWorkerResponse(event.data) ||
        event.data.requestId !== requestId
      ) {
        return;
      }
      this.#finishActive();
      if (event.data.result.ok) {
        const { summary, previewSvg, reportMarkdown } = event.data.result;
        renderSummary(this.#elements.summary, summary);
        if (
          !renderPreview(this.#elements.preview, previewSvg, summary, (findingId) =>
            this.#selectFinding(findingId, true),
          )
        ) {
          this.#showError(INTERNAL_ERROR);
          return;
        }
        renderReport(this.#elements.report, reportMarkdown, (findingId) =>
          this.#selectFinding(findingId, false),
        );
        this.#elements.preview.hidden = false;
        this.#elements.report.hidden = false;
        this.#elements.status.textContent = "Bundle validation complete.";
        this.#elements.status.dataset.state = "ready";
      } else {
        this.#showError(event.data.result.error);
      }
    });
    created.worker.addEventListener("error", () => {
      if (this.#active?.requestId === requestId) {
        this.#finishActive();
        this.#showError(INTERNAL_ERROR);
      }
    });

    if (
      normalized.some(
        (entry) => entry.blob.size > VIEWER_RESOURCE_POLICY.maxArtifactBytes[entry.path],
      ) ||
      normalized.reduce((total, entry) => total + entry.blob.size, 0) >
        VIEWER_RESOURCE_POLICY.maxBundleBytes
    ) {
      this.#finishActive();
      this.#showError(RESOURCE_ERROR);
      return;
    }

    const snapshots: WorkerTransferFile[] = [];
    try {
      for (const entry of normalized) {
        const bytes = await entry.blob.arrayBuffer();
        if (this.#active?.requestId !== requestId) {
          return;
        }
        snapshots.push({ path: entry.path, bytes });
      }
    } catch {
      if (this.#active?.requestId === requestId) {
        this.#finishActive();
        this.#showError(INTERNAL_ERROR);
      }
      return;
    }
    if (this.#active?.requestId !== requestId) {
      return;
    }
    try {
      created.worker.postMessage(
        {
          kind: "boardgate.viewer.validate",
          protocolVersion: VIEWER_PROTOCOL_VERSION,
          requestId,
          files: snapshots,
          policy: VIEWER_RESOURCE_POLICY,
        },
        snapshots.map((entry) => entry.bytes),
      );
    } catch {
      if (this.#active?.requestId === requestId) {
        this.#finishActive();
        this.#showError(INTERNAL_ERROR);
      }
    }
  }

  #cancelActive(): void {
    if (this.#active === undefined) {
      return;
    }
    this.#active.worker.terminate();
    clearTimeout(this.#active.timeoutId);
    URL.revokeObjectURL(this.#active.objectUrl);
    this.#active = undefined;
  }

  #finishActive(): void {
    this.#cancelActive();
  }

  #selectFinding(findingId: string, scrollReport: boolean): void {
    for (const previous of this.#elements.preview.querySelectorAll(".finding-focus")) {
      previous.classList.remove("finding-focus");
    }
    const buttons = [
      ...this.#elements.preview.querySelectorAll<HTMLButtonElement>(".finding-button"),
      ...this.#elements.report.querySelectorAll<HTMLButtonElement>(".report-finding-button"),
    ];
    for (const button of buttons) {
      button.setAttribute(
        "aria-pressed",
        button.dataset.findingId === findingId ? "true" : "false",
      );
    }
    const marker = this.#elements.preview.querySelector<SVGElement>(
      `.preview-canvas [data-finding-id="${CSS.escape(findingId)}"]`,
    );
    if (marker !== null) {
      marker.classList.add("finding-focus");
      marker.scrollIntoView({ block: "nearest" });
    }
    if (scrollReport) {
      this.#elements.report
        .querySelector(`.report-finding-button[data-finding-id="${CSS.escape(findingId)}"]`)
        ?.scrollIntoView({ block: "nearest" });
    }
  }

  #showError(error: ViewerError): void {
    this.#elements.summary.replaceChildren();
    this.#elements.preview.replaceChildren();
    this.#elements.preview.hidden = true;
    this.#elements.report.replaceChildren();
    this.#elements.report.hidden = true;
    this.#elements.status.textContent = "Review unavailable.";
    this.#elements.status.dataset.state = "error";
    const code = document.createElement("code");
    code.textContent = error.code;
    const summary = document.createElement("span");
    summary.textContent = error.summary;
    this.#elements.error.replaceChildren(code, summary);
    this.#elements.error.hidden = false;
  }

  #setNeutral(message: string): void {
    this.#elements.status.textContent = message;
    this.#elements.status.dataset.state = "neutral";
    this.#elements.error.hidden = true;
  }
}

export function createViewerApplication(root: HTMLElement): ViewerController {
  root.replaceChildren();

  const header = document.createElement("header");
  const brand = document.createElement("p");
  brand.className = "eyebrow";
  brand.textContent = "BoardGate";
  const title = document.createElement("h1");
  title.textContent = "Offline review viewer";
  const introduction = document.createElement("p");
  introduction.className = "introduction";
  introduction.textContent =
    "Select one complete six-artifact BoardGate review directory. Files stay in this page and are validated before any engineering summary is shown.";
  header.append(brand, title, introduction);

  const controls = document.createElement("section");
  controls.className = "controls";
  controls.setAttribute("aria-labelledby", "bundle-heading");
  const controlsHeading = document.createElement("h2");
  controlsHeading.id = "bundle-heading";
  controlsHeading.textContent = "Review bundle";
  const chooseButton = document.createElement("button");
  chooseButton.type = "button";
  chooseButton.textContent = "Choose review directory";
  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.setAttribute("webkitdirectory", "");
  input.setAttribute("directory", "");
  input.hidden = true;
  input.setAttribute("aria-label", "Choose BoardGate review directory");
  const privacy = document.createElement("p");
  privacy.className = "privacy";
  privacy.textContent =
    "Offline only: no upload, network request, persistent storage, review execution, or bundle write.";
  controls.append(controlsHeading, chooseButton, input, privacy);

  const state = document.createElement("section");
  state.className = "result";
  state.setAttribute("aria-live", "polite");
  const status = document.createElement("p");
  status.className = "loader-status";
  const error = document.createElement("p");
  error.className = "viewer-error";
  error.hidden = true;
  const summary = document.createElement("div");
  summary.className = "review-summary";
  state.append(status, error, summary);

  const preview = document.createElement("section");
  preview.className = "preview";
  preview.hidden = true;

  const report = document.createElement("section");
  report.className = "report";
  report.hidden = true;

  const footer = document.createElement("footer");
  footer.textContent = `Viewer ${__BOARDGATE_VIEWER_VERSION__} · Evidence remains read-only.`;

  root.append(header, controls, state, preview, report, footer);
  const controller = new ViewerController(
    { input, chooseButton, status, summary, preview, report, error },
    __BOARDGATE_WORKER_SOURCE__,
  );
  controller.start();
  return controller;
}

const root = document.querySelector<HTMLElement>("#boardgate-viewer");
if (root !== null) {
  createViewerApplication(root);
}
