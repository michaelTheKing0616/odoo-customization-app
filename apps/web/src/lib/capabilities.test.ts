import { describe, expect, it } from "vitest";
import type { CapabilityMatrix, Connection } from "./api";
import {
  advancedMutationAllowed,
  advancedMutationBlockedReason,
  belowMinMajor,
  bindModeCapabilityId,
  bindModeSupported,
  bindModeUnsupportedReason,
  connectionMajor,
  connectionSupports,
  connectionUnsupportedReason,
  currencyFieldSupported,
  currencyFieldUnsupportedReason,
  defaultWindowViewMode,
  injectStrategyCapabilityId,
  isEnterpriseEdition,
  isExperimentalMajor,
  mutationAllowed,
  mutationBlockedReason,
  scaffoldApplyAllowed,
  scaffoldApplyBlockedReason,
  scaffoldOptsFromSpec,
} from "./capabilities";

function matrix(
  partial: Partial<CapabilityMatrix> & Pick<CapabilityMatrix, "major" | "ga">,
): CapabilityMatrix {
  return {
    edition: "community",
    server_version: `${partial.major}.0`,
    message: `mock major ${partial.major}`,
    supported: [],
    unsupported: [],
    ...partial,
  };
}

function conn(capabilities: CapabilityMatrix | null | undefined): Connection {
  return {
    id: "mock",
    name: "Mock",
    url: "http://127.0.0.1:8069",
    db_name: "odoo_dev",
    username: "admin",
    server_version: capabilities?.server_version ?? null,
    created_at: null,
    updated_at: null,
    capabilities: capabilities ?? null,
  };
}

/** Mirrors API `capabilities_from_version("16.0")` / ODOO_16_CAPABILITIES. */
function mockOdoo16Connection(): Connection {
  return conn(
    matrix({
      major: 16,
      ga: false,
      server_version: "16.0",
      message: "Odoo 16 Community — experimental",
      supported: [
        "base_automation_safe_triggers",
        "list_tree_fallback",
        "object_create_crud_model",
        "smart_button_inherit_box",
        "view_inject_inherit",
        "view_inject_mutate",
      ],
      unsupported: [
        {
          id: "related_write_dotted_path",
          label: "Related write (dotted update_path)",
          reason: "Not available on Odoo 16 (community)",
        },
        {
          id: "object_write_update_path",
          label: "Update field (object_write)",
          reason: "Not available on Odoo 16 (community)",
        },
        {
          id: "list_as_list_type",
          label: "List as list type",
          reason: "Not available on Odoo 16 (community)",
        },
      ],
    }),
  );
}

function mockGaMajor(
  major: 17 | 18 | 19,
  opts?: { edition?: string; extraSupported?: string[] },
): Connection {
  const listCap =
    major >= 18
      ? (["list_as_list_type"] as string[])
      : ([] as string[]);
  return conn(
    matrix({
      major,
      ga: true,
      edition: opts?.edition ?? "community",
      server_version: opts?.edition === "enterprise" ? `${major}.0+e` : `${major}.0`,
      supported: [
        "base_automation_safe_triggers",
        "list_tree_fallback",
        "object_create_crud_model",
        "object_write_update_path",
        "related_write_dotted_path",
        "smart_button_inherit_box",
        "view_inject_inherit",
        "view_inject_mutate",
        ...listCap,
        ...(opts?.extraSupported ?? []),
      ],
      unsupported:
        major <= 17
          ? [
              {
                id: "list_as_list_type",
                label: "List as list type",
                reason: `Not available on Odoo ${major}`,
              },
            ]
          : [],
    }),
  );
}

describe("connectionSupports (fail-closed)", () => {
  it.each([
    [null, "object_write_update_path"],
    [undefined, "related_write_dotted_path"],
  ] as const)("returns false when connection is %s", (c, cap) => {
    expect(connectionSupports(c, cap)).toBe(false);
  });

  it("returns false when capabilities are missing on connection", () => {
    expect(
      connectionSupports({ ...mockOdoo16Connection(), capabilities: null }, "view_inject_inherit"),
    ).toBe(false);
    expect(
      connectionSupports({ ...mockOdoo16Connection(), capabilities: undefined }, "view_inject_inherit"),
    ).toBe(false);
  });

  it("returns probe hint when capabilities unknown", () => {
    expect(connectionUnsupportedReason(null, "related_write_dotted_path")).toBe(
      "Version capabilities unknown — probe the connection on Connect / Browse",
    );
    expect(
      connectionUnsupportedReason(
        { ...mockOdoo16Connection(), capabilities: null },
        "object_write_update_path",
      ),
    ).toMatch(/unknown/i);
  });

  it("returns registry reason when cap is listed unsupported", () => {
    const c16 = mockOdoo16Connection();
    expect(connectionUnsupportedReason(c16, "object_write_update_path")).toBe(
      "Not available on Odoo 16 (community)",
    );
  });

  it("returns generic reason when cap absent from both lists", () => {
    const c16 = mockOdoo16Connection();
    expect(connectionUnsupportedReason(c16, "totally_unknown_cap")).toBe(
      "Unavailable on this Odoo version",
    );
  });

  it("Odoo 16 mock omits update_path-era automation caps", () => {
    const c16 = mockOdoo16Connection();
    expect(connectionSupports(c16, "related_write_dotted_path")).toBe(false);
    expect(connectionSupports(c16, "object_write_update_path")).toBe(false);
    expect(connectionSupports(c16, "object_create_crud_model")).toBe(true);
    expect(connectionSupports(c16, "view_inject_inherit")).toBe(true);
    expect(connectionSupports(c16, "list_as_list_type")).toBe(false);
  });

  it.each([17, 18, 19] as const)(
    "GA major %i supports update_path-era caps",
    (major) => {
      const c = mockGaMajor(major);
      expect(connectionSupports(c, "object_write_update_path")).toBe(true);
      expect(connectionSupports(c, "related_write_dotted_path")).toBe(true);
      expect(connectionSupports(c, "object_create_crud_model")).toBe(true);
    },
  );
});

describe("edition / experimental helpers", () => {
  it("isEnterpriseEdition is case-insensitive and fail-closed on missing", () => {
    expect(isEnterpriseEdition(undefined)).toBe(false);
    expect(isEnterpriseEdition(null)).toBe(false);
    expect(isEnterpriseEdition(matrix({ major: 19, ga: true, edition: "community" }))).toBe(
      false,
    );
    expect(
      isEnterpriseEdition(matrix({ major: 19, ga: true, edition: "enterprise" })),
    ).toBe(true);
    expect(
      isEnterpriseEdition(matrix({ major: 18, ga: true, edition: "Enterprise" })),
    ).toBe(true);
  });

  it("isExperimentalMajor tracks ga flag (16 experimental; 17–19 GA)", () => {
    expect(isExperimentalMajor(undefined)).toBe(false);
    expect(isExperimentalMajor(null)).toBe(false);
    expect(isExperimentalMajor(mockOdoo16Connection().capabilities)).toBe(true);
    expect(isExperimentalMajor(mockGaMajor(17).capabilities)).toBe(false);
    expect(isExperimentalMajor(mockGaMajor(19).capabilities)).toBe(false);
  });

  it("enterprise edition does not change mutationAllowed / scaffold base gates", () => {
    const ent = mockGaMajor(19, { edition: "enterprise" });
    expect(isEnterpriseEdition(ent.capabilities)).toBe(true);
    expect(mutationAllowed(ent)).toBe(true);
    expect(advancedMutationAllowed(ent)).toBe(true);
    expect(scaffoldApplyAllowed(ent)).toBe(true);
    expect(scaffoldApplyAllowed(ent, { requireObjectWrite: true })).toBe(true);
  });
});

describe("connectionMajor + belowMinMajor", () => {
  it("connectionMajor returns null when unprobed", () => {
    expect(connectionMajor(null)).toBeNull();
    expect(connectionMajor(undefined)).toBeNull();
    expect(connectionMajor(conn(null))).toBeNull();
    expect(
      connectionMajor(
        conn(matrix({ major: null as unknown as number, ga: false, supported: [] })),
      ),
    ).toBeNull();
  });

  it.each([
    [16, 16, false],
    [16, 17, true],
    [16, 19, true],
    [17, 16, false],
    [17, 17, false],
    [17, 18, true],
    [18, 19, true],
    [19, 19, false],
    [19, 20, true],
  ] as const)(
    "major %i vs min_major %i → belowMinMajor=%s",
    (major, minMajor, expected) => {
      const c =
        major === 16 ? mockOdoo16Connection() : mockGaMajor(major as 17 | 18 | 19);
      expect(belowMinMajor(c, minMajor)).toBe(expected);
    },
  );

  it("belowMinMajor fails closed when major unknown; null min_major never blocks", () => {
    expect(belowMinMajor(null, 16)).toBe(true);
    expect(belowMinMajor(conn(null), 19)).toBe(true);
    expect(belowMinMajor(mockOdoo16Connection(), null)).toBe(false);
    expect(belowMinMajor(mockOdoo16Connection(), undefined)).toBe(false);
    expect(belowMinMajor(null, null)).toBe(false);
  });
});

describe("currencyFieldSupported", () => {
  it("fails closed when major unknown", () => {
    expect(currencyFieldSupported(null)).toBe(false);
    expect(currencyFieldSupported(conn(null))).toBe(false);
    expect(currencyFieldUnsupportedReason(null)).toMatch(/unknown/i);
  });

  it.each([
    [16, false],
    [17, true],
    [18, true],
    [19, true],
  ] as const)("major %i → currencyFieldSupported=%s", (major, expected) => {
    const c =
      major === 16 ? mockOdoo16Connection() : mockGaMajor(major as 17 | 18 | 19);
    expect(currencyFieldSupported(c)).toBe(expected);
    if (!expected) {
      expect(currencyFieldUnsupportedReason(c)).toMatch(/currency_field/i);
    } else {
      expect(currencyFieldUnsupportedReason(c)).toBeNull();
    }
  });
});

describe("bindModeSupported", () => {
  it("maps modes to capability ids", () => {
    expect(bindModeCapabilityId("create_update")).toBe("object_write_update_path");
    expect(bindModeCapabilityId("create_related")).toBe("object_create_crud_model");
    expect(bindModeCapabilityId("create_smart")).toBe("smart_button_inherit_box");
    expect(bindModeCapabilityId("create_activity")).toBeNull();
    expect(bindModeCapabilityId("create_mail")).toBeNull();
    expect(bindModeCapabilityId("bind_existing")).toBeNull();
  });

  it("create_update follows object_write_update_path on major 16", () => {
    const c16 = mockOdoo16Connection();
    expect(bindModeSupported(c16, "create_update")).toBe(false);
    expect(bindModeUnsupportedReason(c16, "create_update")).toMatch(
      /Not available on Odoo 16/i,
    );
  });

  it("modes without cap id allow on GA only (fail-closed missing + experimental)", () => {
    expect(bindModeSupported(null, "create_activity")).toBe(false);
    expect(bindModeSupported(conn(null), "create_mail")).toBe(false);
    expect(bindModeSupported(mockOdoo16Connection(), "create_activity")).toBe(false);
    expect(bindModeUnsupportedReason(mockOdoo16Connection(), "bind_existing")).toMatch(
      /experimental Odoo 16/i,
    );
    expect(bindModeSupported(mockGaMajor(19), "create_activity")).toBe(true);
    expect(bindModeUnsupportedReason(mockGaMajor(19), "create_activity")).toBeNull();
  });

  it("create_related / create_smart follow exact caps on 16", () => {
    const c16 = mockOdoo16Connection();
    expect(bindModeSupported(c16, "create_related")).toBe(true);
    expect(bindModeSupported(c16, "create_smart")).toBe(true);
  });
});

describe("mutationAllowed / advancedMutationAllowed", () => {
  it("mutationAllowed fail-closed when capabilities missing", () => {
    expect(mutationAllowed(null)).toBe(false);
    expect(mutationAllowed(undefined)).toBe(false);
    expect(mutationAllowed(conn(null))).toBe(false);
    expect(mutationBlockedReason(null)).toBe(
      "Version capabilities unknown — probe the connection on Connect / Browse",
    );
  });

  it("allows primary mutate once major-16 caps are probed", () => {
    const c16 = mockOdoo16Connection();
    expect(mutationAllowed(c16)).toBe(true);
    expect(mutationBlockedReason(c16)).toBeNull();
  });

  it("advancedMutationAllowed greys out on experimental major-16 and missing caps", () => {
    expect(advancedMutationAllowed(mockOdoo16Connection())).toBe(false);
    expect(advancedMutationAllowed(null)).toBe(false);
    expect(advancedMutationBlockedReason(mockOdoo16Connection())).toMatch(
      /experimental Odoo 16/i,
    );
    expect(advancedMutationBlockedReason(null)).toMatch(/unknown/i);
  });

  it.each([17, 18, 19] as const)(
    "advancedMutationAllowed true on GA major %i",
    (major) => {
      expect(advancedMutationAllowed(mockGaMajor(major))).toBe(true);
      expect(advancedMutationBlockedReason(mockGaMajor(major))).toBeNull();
    },
  );
});

describe("scaffoldApplyAllowed", () => {
  it("requires probed caps + create + inherit", () => {
    expect(scaffoldApplyAllowed(null)).toBe(false);
    expect(scaffoldApplyBlockedReason(null)).toMatch(/unknown/i);
    expect(scaffoldApplyAllowed(mockOdoo16Connection())).toBe(true);
  });

  it("object_write / related_write greys out on major-16", () => {
    const c16 = mockOdoo16Connection();
    expect(scaffoldApplyAllowed(c16, { requireObjectWrite: true })).toBe(false);
    expect(
      scaffoldApplyBlockedReason(c16, { requireObjectWrite: true }),
    ).toMatch(/object_write|Not available|Unavailable/i);
    expect(scaffoldApplyAllowed(c16, { requireRelatedWrite: true })).toBe(false);
    expect(
      scaffoldApplyBlockedReason(c16, { requireRelatedWrite: true }),
    ).toMatch(/related_write|Not available|Unavailable/i);
  });

  it.each([17, 18, 19] as const)(
    "scaffold with object+related write allowed on GA %i",
    (major) => {
      const c = mockGaMajor(major);
      expect(
        scaffoldApplyAllowed(c, {
          requireObjectWrite: true,
          requireRelatedWrite: true,
        }),
      ).toBe(true);
      expect(
        scaffoldApplyBlockedReason(c, {
          requireObjectWrite: true,
          requireRelatedWrite: true,
        }),
      ).toBeNull();
    },
  );

  it("scaffoldOptsFromSpec detects update_path-era needs", () => {
    expect(
      scaffoldOptsFromSpec({
        automations: [{ kind: "related_write", field: "x_partner_id.email" }],
      }),
    ).toEqual({ requireObjectWrite: false, requireRelatedWrite: true });
    expect(
      scaffoldOptsFromSpec({
        automations: [{ kind: "update_field", field: "x_note" }],
      }),
    ).toEqual({ requireObjectWrite: true, requireRelatedWrite: false });
    expect(
      scaffoldOptsFromSpec({
        automations: [{ kind: "object_write", field: "x_note" }],
      }),
    ).toEqual({ requireObjectWrite: true, requireRelatedWrite: false });
    expect(
      scaffoldOptsFromSpec({
        automations: [{ kind: "create_activity", field: "x_partner_id.email" }],
      }),
    ).toEqual({ requireObjectWrite: false, requireRelatedWrite: true });
    expect(scaffoldOptsFromSpec(null)).toEqual({
      requireObjectWrite: false,
      requireRelatedWrite: false,
    });
    expect(scaffoldOptsFromSpec({ automations: "bad" as unknown as never[] })).toEqual({
      requireObjectWrite: false,
      requireRelatedWrite: false,
    });
  });
});

describe("defaultWindowViewMode", () => {
  it.each([
    [16, "tree,form"],
    [17, "tree,form"],
    [18, "list,form"],
    [19, "list,form"],
  ] as const)("major %i → %s", (major, expected) => {
    const c =
      major === 16 ? mockOdoo16Connection() : mockGaMajor(major as 17 | 18 | 19);
    expect(defaultWindowViewMode(c)).toBe(expected);
  });

  it("falls back to tree,form when caps missing (fail-closed list_as_list_type)", () => {
    expect(defaultWindowViewMode(null)).toBe("tree,form");
    expect(defaultWindowViewMode(conn(null))).toBe("tree,form");
  });
});

describe("injectStrategyCapabilityId", () => {
  it("maps inherit/mutate", () => {
    expect(injectStrategyCapabilityId("inherit")).toBe("view_inject_inherit");
    expect(injectStrategyCapabilityId("mutate")).toBe("view_inject_mutate");
  });
});

describe("hosting_hint / python_module_install matrix fields (M1 honesty)", () => {
  it("Online matrix fields must not silently block GA mutations", () => {
    const online = conn(
      matrix({
        major: 19,
        ga: true,
        hosting_hint: "online",
        python_module_install: false,
        warnings: ["Custom Python module install is not available on Odoo Online"],
        message:
          "Hosting looks like Odoo Online: metadata customization and data/XML module import are OK",
        supported: [
          "base_automation_safe_triggers",
          "list_as_list_type",
          "list_tree_fallback",
          "object_create_crud_model",
          "object_write_update_path",
          "related_write_dotted_path",
          "smart_button_inherit_box",
          "view_inject_inherit",
          "view_inject_mutate",
        ],
        unsupported: [],
      }),
    );
    expect(online.capabilities?.hosting_hint).toBe("online");
    expect(online.capabilities?.python_module_install).toBe(false);
    // Metadata mutations remain allowed; only Python promote is refused server-side.
    expect(mutationAllowed(online)).toBe(true);
    expect(advancedMutationAllowed(online)).toBe(true);
    expect(scaffoldApplyAllowed(online)).toBe(true);
  });

  it("self_hosted + python_module_install true keeps experimental-16 advanced grey-out", () => {
    const c16 = conn(
      matrix({
        major: 16,
        ga: false,
        hosting_hint: "self_hosted",
        python_module_install: true,
        server_version: "16.0",
        message: "Odoo 16 Community — experimental",
        supported: [
          "base_automation_safe_triggers",
          "list_tree_fallback",
          "object_create_crud_model",
          "smart_button_inherit_box",
          "view_inject_inherit",
          "view_inject_mutate",
        ],
        unsupported: [
          {
            id: "related_write_dotted_path",
            label: "Related write (dotted update_path)",
            reason: "Not available on Odoo 16 (community)",
          },
          {
            id: "object_write_update_path",
            label: "Update field (object_write)",
            reason: "Not available on Odoo 16 (community)",
          },
          {
            id: "list_as_list_type",
            label: "List as list type",
            reason: "Not available on Odoo 16 (community)",
          },
        ],
      }),
    );
    expect(c16.capabilities?.hosting_hint).toBe("self_hosted");
    expect(c16.capabilities?.python_module_install).toBe(true);
    expect(mutationAllowed(c16)).toBe(true);
    expect(advancedMutationAllowed(c16)).toBe(false);
  });
});
