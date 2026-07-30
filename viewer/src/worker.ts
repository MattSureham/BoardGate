/// <reference lib="webworker" />

import {
  type ValidationResult,
  VIEWER_PROTOCOL_VERSION,
  type ViewerWorkerRequest,
  type ViewerWorkerResponse,
} from "./contracts";
import { admitTransferredBundle } from "./validation";
import { failureFrom, reject } from "./validation/errors";

declare const self: DedicatedWorkerGlobalScope;

self.addEventListener("message", (event: MessageEvent<ViewerWorkerRequest>) => {
  void handleRequest(event.data);
});

async function handleRequest(request: ViewerWorkerRequest): Promise<void> {
  let result: ValidationResult;
  try {
    if (
      request.kind !== "boardgate.viewer.validate" ||
      request.protocolVersion !== VIEWER_PROTOCOL_VERSION ||
      typeof request.requestId !== "string" ||
      request.requestId.length === 0 ||
      !Array.isArray(request.files)
    ) {
      reject("ARTIFACT_INVENTORY_MISMATCH");
    }
    const files = new Map<string, ArrayBuffer>();
    for (const entry of request.files) {
      if (
        typeof entry.path !== "string" ||
        !(entry.bytes instanceof ArrayBuffer) ||
        files.has(entry.path)
      ) {
        reject("ARTIFACT_INVENTORY_MISMATCH");
      }
      files.set(entry.path, entry.bytes);
    }
    result = await admitTransferredBundle(files, request.policy);
  } catch (error) {
    result = failureFrom(error);
  }
  const response: ViewerWorkerResponse = {
    kind: "boardgate.viewer.result",
    protocolVersion: VIEWER_PROTOCOL_VERSION,
    requestId: typeof request.requestId === "string" ? request.requestId : "invalid-request",
    result,
  };
  self.postMessage(response);
}
