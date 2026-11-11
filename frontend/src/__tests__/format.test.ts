import { describe, expect, it } from "vitest";

import { formatResetDate } from "@/lib/format";

describe("formatResetDate", () => {
  it("shows the day the quota resets", () => {
    expect(formatResetDate("2026-12-01T00:00:00Z")).toBe("1 December 2026");
    expect(formatResetDate("2027-01-01T00:00:00+00:00")).toBe("1 January 2027");
  });

  it("keeps the text when it is not a date", () => {
    expect(formatResetDate("soon")).toBe("soon");
  });
});
