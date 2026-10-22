import { describe, expect, it } from "vitest";
import {
  formatQwebRenderErrorDisplay,
  parseQwebRenderError,
} from "./reportRenderError";

describe("parseQwebRenderError", () => {
  it("names the template line when present", () => {
    const info = parseQwebRenderError(
      'Error to render compiling AST\nFile "report_invoice", line 42, in template',
    );
    expect(info.templateLine).toBe(42);
    expect(info.summary).toBe("QWeb render error at template line 42");
  });

  it("keeps the message when no line is present", () => {
    const info = parseQwebRenderError("wkhtmltopdf failed");
    expect(info.templateLine).toBeNull();
    expect(info.summary).toBe("QWeb render error");
  });

  it("format display leads with the named line", () => {
    const display = formatQwebRenderErrorDisplay(
      "QWebException: Error at line 17 in account.report_invoice",
    );
    expect(display).toMatch(/template line 17/i);
    expect(display).toMatch(/QWebException/);
  });
});
