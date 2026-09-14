import { describe, expect, it } from "vitest";
import { isApiNotFound } from "./api-error";

describe("isApiNotFound", () => {
  it("matches FastAPI 404s including METHOD path", () => {
    expect(isApiNotFound(new Error("Not Found (POST /api/ai/option-a/reverify)"))).toBe(
      true,
    );
    expect(isApiNotFound(new Error("Not Found"))).toBe(true);
    expect(isApiNotFound(new Error("Request failed (404)"))).toBe(true);
  });

  it("does not treat Odoo Model not found as our API 404", () => {
    expect(isApiNotFound(new Error("Model not found: sale.order"))).toBe(false);
  });
});
