import { describe, expect, it } from "vitest";
import { fmt } from "./fmt";

describe("fmt.n", () => {
  it("formats with locale thousands separators", () => {
    expect(fmt.n(1234567)).toBe("1,234,567");
  });
  it("handles zero", () => {
    expect(fmt.n(0)).toBe("0");
  });
});

describe("fmt.k", () => {
  it("returns raw under 1000", () => {
    expect(fmt.k(42)).toBe("42");
    expect(fmt.k(999)).toBe("999");
  });
  it("formats K scale", () => {
    expect(fmt.k(1200)).toBe("1.2K");
    expect(fmt.k(9999)).toBe("10.0K");
  });
  it("formats M scale", () => {
    expect(fmt.k(1_500_000)).toBe("1.50M");
  });
  it("formats B scale", () => {
    expect(fmt.k(1_500_000_000)).toBe("1.50B");
  });
});

describe("fmt.usd", () => {
  it("formats with 2-decimal precision + leading $", () => {
    expect(fmt.usd(0)).toBe("$0.00");
    expect(fmt.usd(12.3)).toBe("$12.30");
    expect(fmt.usd(0.001)).toBe("$0.00");
  });
});

describe("fmt.pct", () => {
  it("scales to percent with 1 decimal", () => {
    expect(fmt.pct(0.5)).toBe("50.0%");
    expect(fmt.pct(0.123)).toBe("12.3%");
  });
});

describe("fmt.delta", () => {
  it("adds + for non-negative", () => {
    expect(fmt.delta(0.1)).toBe("+10.0%");
    expect(fmt.delta(0)).toBe("+0.0%");
  });
  it("negatives keep the minus, no + prefix", () => {
    expect(fmt.delta(-0.12)).toBe("-12.0%");
  });
});
