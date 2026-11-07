import { describe, expect, it } from "vitest";

import { imageDataUri } from "@/lib/pdf";

describe("imageDataUri", () => {
  it("recognizes a JPEG", () => {
    expect(imageDataUri("/9j/4AAQ")).toBe("data:image/jpeg;base64,/9j/4AAQ");
  });

  it("uses PNG for anything else", () => {
    expect(imageDataUri("iVBORw0KGgo=")).toBe("data:image/png;base64,iVBORw0KGgo=");
  });
});
