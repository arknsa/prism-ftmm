/**
 * Tests for buildQueryString (lib/filter-context.tsx).
 *
 * Pure function — no React rendering required.
 * Covers: empty params, single param, multi-param, URL encoding, empty-value filtering.
 */

import { describe, expect, it } from "vitest";

import { buildQueryString } from "@/lib/filter-context";

describe("buildQueryString", () => {
  it("returns empty string when params is empty", () => {
    expect(buildQueryString({})).toBe("");
  });

  it("returns empty string when all values are empty strings", () => {
    expect(buildQueryString({ country: "", study_program_id: "" })).toBe("");
  });

  it("builds a single-param query string with leading ?", () => {
    const result = buildQueryString({ country: "Indonesia" });
    expect(result).toBe("?country=Indonesia");
  });

  it("builds a multi-param query string", () => {
    const result = buildQueryString({
      study_program_id: "2",
      country: "Indonesia",
    });
    expect(result).toMatch(/^\?/);
    expect(result).toContain("country=Indonesia");
    expect(result).toContain("study_program_id=2");
  });

  it("URL-encodes values with spaces", () => {
    const result = buildQueryString({ country: "United States" });
    // URLSearchParams encodes spaces as '+'
    expect(result).toContain("United");
    expect(result).not.toContain(" ");
  });

  it("omits entries whose value is an empty string", () => {
    const result = buildQueryString({
      country: "",
      graduation_year: "2022",
    });
    expect(result).toBe("?graduation_year=2022");
    expect(result).not.toContain("country");
  });
});
