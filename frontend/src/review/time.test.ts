import { expect, it } from "vitest";

import { normalizeEditedTime } from "./time";

it("normalizes only defensible time formatting and preserves uncertainty", () => {
  expect(normalizeEditedTime("8:05")).toBe("08:05");
  expect(normalizeEditedTime("+03:00d")).toBe("03:00");
  expect(normalizeEditedTime("14:56c")).toBe("14:56");
  expect(normalizeEditedTime("0?:25")).toBe("0?:25");
  expect(normalizeEditedTime("29:80")).toBe("??:??");
  expect(normalizeEditedTime("texto")).toBe("texto");
});
