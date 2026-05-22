import { describe, expect, it } from "vitest";

import { OPERATION_WAIT_OVERLAY_LAYER_CLASS } from "./operation-wait-overlay-constants";

describe("OperationWaitOverlay", () => {
  it("uses an app-top layer above dialogs", () => {
    expect(OPERATION_WAIT_OVERLAY_LAYER_CLASS).toContain("z-[9999]");
  });
});
