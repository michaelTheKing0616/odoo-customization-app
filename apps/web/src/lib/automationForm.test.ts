import { describe, expect, it } from "vitest";
import type { Connection } from "@/lib/api";
import {
  composerSessionState,
  defaultComposerForm,
  designerHref,
  firstAvailableSafeActionKind,
  isComposerDirty,
  parseFieldValueLines,
  parseIdList,
  parseNameList,
  triggerLabel,
} from "./automationForm";

function mockConnection(supported: string[]): Connection {
  return {
    id: "c1",
    name: "Test",
    url: "http://127.0.0.1:8069",
    db_name: "odoo_dev",
    username: "admin",
    server_version: "19.0",
    write_mode: "standard",
    created_at: null,
    updated_at: null,
    capabilities: {
      major: 19,
      edition: "community",
      server_version: "19.0",
      ga: true,
      message: "ok",
      supported,
      unsupported: [],
    },
  };
}

describe("automationForm parsers", () => {
  it("parses key=value lines and skips comments", () => {
    expect(
      parseFieldValueLines("# skip\nsummary=Follow up\nnote=Created by automation\n=bad\n"),
    ).toEqual({ summary: "Follow up", note: "Created by automation" });
  });

  it("parses id and name lists", () => {
    expect(parseIdList("3, 7 12, -1, x")).toEqual([3, 7, 12]);
    expect(parseNameList("name, email phone")).toEqual(["name", "email", "phone"]);
  });
});

describe("automationForm session", () => {
  it("marks dirty when the composer diverges from baseline", () => {
    const baseline = defaultComposerForm("res.partner");
    expect(isComposerDirty(baseline, baseline)).toBe(false);
    expect(isComposerDirty({ ...baseline, name: "Set note" }, baseline)).toBe(true);
  });

  it("maps dirty / saved flags to session state", () => {
    expect(composerSessionState({ dirty: true, savedOnce: false })).toBe("unsaved");
    expect(composerSessionState({ dirty: false, savedOnce: true })).toBe("saved");
    expect(composerSessionState({ dirty: false, savedOnce: false })).toBe("draft");
  });

  it("labels triggers in sentence case", () => {
    expect(triggerLabel("on_write")).toBe("On update");
    expect(triggerLabel("unknown")).toBe("unknown");
  });

  it("builds a designer deep link for the same model", () => {
    expect(designerHref("abc", "x_lib_loan")).toBe(
      "/connections/abc/designer?model=x_lib_loan",
    );
    expect(designerHref("abc", "  ")).toBe("/connections/abc/designer");
  });
});

describe("automationForm capability fallback", () => {
  it("falls back to create_activity when update_path is missing", () => {
    const conn = mockConnection(["object_create_crud_model"]);
    expect(firstAvailableSafeActionKind(conn)).toBe("create_activity");
  });

  it("prefers update_field when the capability is present", () => {
    const conn = mockConnection(["object_write_update_path", "object_create_crud_model"]);
    expect(firstAvailableSafeActionKind(conn)).toBe("update_field");
  });

  it("fail-closes to create_activity when capabilities are unknown", () => {
    expect(firstAvailableSafeActionKind(null)).toBe("create_activity");
  });
});
