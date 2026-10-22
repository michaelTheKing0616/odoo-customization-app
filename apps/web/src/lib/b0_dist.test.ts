// @vitest-environment node
/**
 * B0-DIST oracle. Locked: the Worker does not edit this file.
 *
 * AC1–AC4 pin the card decision table: `dev` stays on `.next`; every
 * `next build` script sets its own other distDir; git ignores those dirs.
 * AC5 and AC6 are not pinned (Oracle packet). A guessed Connect or
 * plan-idempotency assertion would lock the wrong behaviour.
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD } from "next/constants";
import { expect, test, vi } from "vitest";

const DEV_DIST = ".next";
const WEB_ROOT = path.resolve(__dirname, "../..");
const REPO_ROOT = path.resolve(WEB_ROOT, "../..");
const DEV_ROUTES = ["/", "/connect", "/settings"] as const;

type Assignment = { key: string; value: string };
type Invocation = { name: string; text: string };

function read(file: string): string {
  return fs.readFileSync(file, "utf8");
}

function normalizeDist(raw: string): string {
  let value = raw.trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  value = value.replace(/\$\{[^}]+\}/g, "3010");
  return value.replace(/\/+$/, "");
}

function isSeparateDistDir(raw: string): boolean {
  const dir = normalizeDist(raw);
  if (!dir || dir === DEV_DIST) return false;
  if (dir.startsWith("/") || dir.includes("..") || /\s/.test(dir) || dir.includes("://")) {
    return false;
  }
  if (!/^[A-Za-z0-9._@-]+$/.test(dir)) return false;
  return /[A-Za-z.]/.test(dir);
}

function isDistKey(key: string): boolean {
  return key === "distDir" || key.endsWith("DIST_DIR");
}

function assignments(script: string): Assignment[] {
  const found: Assignment[] = [];
  const envRe = /([A-Za-z_][A-Za-z0-9_]*)=(?:"([^"]*)"|'([^']*)'|([^\s;&]+))/g;
  for (const match of script.matchAll(envRe)) {
    found.push({ key: match[1], value: match[2] ?? match[3] ?? match[4] ?? "" });
  }
  const propRe = /([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)/g;
  for (const match of script.matchAll(propRe)) {
    found.push({ key: match[1], value: match[2] ?? match[3] ?? match[4] ?? "" });
  }
  return found;
}

/** Directories a script itself names. A boolean flag is not a distDir. */
function explicitBuildDists(script: string): string[] {
  const found = new Set<string>();
  for (const assignment of assignments(script)) {
    if (!isDistKey(assignment.key)) continue;
    if (!isSeparateDistDir(assignment.value)) continue;
    found.add(normalizeDist(assignment.value));
  }
  return [...found];
}

function distEnv(script: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const assignment of assignments(script)) {
    if (!isDistKey(assignment.key) || assignment.key === "distDir") continue;
    if (!isSeparateDistDir(assignment.value)) continue;
    env[assignment.key] = normalizeDist(assignment.value);
  }
  return env;
}

function allEnv(script: string): Record<string, string> {
  const env: Record<string, string> = {};
  for (const assignment of assignments(script)) {
    if (!/^[A-Z][A-Z0-9_]*$/.test(assignment.key)) continue;
    const value = assignment.value.trim();
    if (!value || /\s/.test(value) || value.includes("://")) continue;
    env[assignment.key] = value;
  }
  return env;
}

function literalDistDirs(text: string): string[] {
  const found = new Set<string>();
  const re = /distDir\s*:\s*(?:"([^"]+)"|'([^']+)'|`([^`]+)`)/g;
  for (const match of text.matchAll(re)) {
    const value = match[1] ?? match[2] ?? match[3] ?? "";
    if (isSeparateDistDir(value)) found.add(normalizeDist(value));
  }
  return [...found];
}

function runsNextBuild(text: string): boolean {
  return /\bnext\s+build\b/.test(text);
}

function webServerText(): string {
  const source = read(path.join(WEB_ROOT, "playwright.config.ts"));
  const start = source.indexOf("webServer:");
  if (start < 0) return "";
  return source.slice(start);
}

function packageScripts(): Invocation[] {
  const found: Invocation[] = [];
  const files = [
    path.join(REPO_ROOT, "package.json"),
    path.join(WEB_ROOT, "package.json"),
  ];
  for (const file of files) {
    if (!fs.existsSync(file)) continue;
    const pkg = JSON.parse(read(file)) as { scripts?: Record<string, unknown> };
    const rel = path.relative(REPO_ROOT, file);
    for (const [name, script] of Object.entries(pkg.scripts ?? {})) {
      if (typeof script === "string" && runsNextBuild(script)) {
        found.push({ name: `${rel}:${name}`, text: script });
      }
    }
  }
  return found;
}

function shellInvocations(): Invocation[] {
  const roots = [
    path.join(REPO_ROOT, ".github", "workflows"),
    path.join(REPO_ROOT, "scripts"),
    path.join(WEB_ROOT, "scripts"),
  ];
  const found: Invocation[] = [];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const file of walk(root)) {
      const text = read(file);
      const commands = text
        .split("\n")
        .filter((line) => {
          const trimmed = line.trim();
          return trimmed.length > 0 && !trimmed.startsWith("#") && !trimmed.startsWith("//");
        })
        .join("\n");
      if (runsNextBuild(commands)) {
        found.push({ name: path.relative(REPO_ROOT, file), text: commands });
      }
    }
  }
  return found;
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...walk(full));
      continue;
    }
    if (/\.(sh|yml|yaml|mjs|cjs)$/.test(entry.name)) out.push(full);
  }
  return out;
}

function buildInvocations(): Invocation[] {
  const playwright = webServerText();
  const found = packageScripts();
  if (runsNextBuild(playwright)) {
    found.push({ name: "apps/web/playwright.config.ts:webServer", text: playwright });
  }
  found.push(...shellInvocations());
  return found;
}

type NextConfigLike = { distDir?: string };
type NextConfigFactory = (
  phase: string,
  ctx: { defaultConfig: NextConfigLike },
) => NextConfigLike | Promise<NextConfigLike>;

async function loadDistDir(env: Record<string, string>, phase: string): Promise<string> {
  const keys = new Set<string>(["INGENIUM_DIST_DIR", "PLAYWRIGHT_E2E_BUILD", ...Object.keys(env)]);
  const previous = new Map<string, string | undefined>();
  for (const key of keys) previous.set(key, process.env[key]);
  try {
    for (const key of keys) delete process.env[key];
    for (const [key, value] of Object.entries(env)) process.env[key] = value;
    vi.resetModules();
    const imported = (await import("../../next.config.ts")) as {
      default: NextConfigLike | NextConfigFactory;
    };
    const loaded = imported.default;
    const config = await Promise.resolve(
      typeof loaded === "function" ? loaded(phase, { defaultConfig: {} }) : loaded,
    );
    const dir = config.distDir ? normalizeDist(config.distDir) : DEV_DIST;
    return dir || DEV_DIST;
  } finally {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    vi.resetModules();
  }
}

/** True only when the script text names the directory next.config then uses. */
async function scriptIsolates(script: string): Promise<boolean> {
  const explicit = explicitBuildDists(script);
  if (explicit.length === 0) return false;
  const effective = await loadDistDir(distEnv(script), PHASE_PRODUCTION_BUILD);
  return explicit.includes(effective);
}

function holdsAc3(devDist: string, buildDist: string): boolean {
  return devDist === DEV_DIST && buildDist !== DEV_DIST && buildDist !== devDist;
}

/** Pattern `.next/` matches the dev directory only, not `.next-e2e` or `.next-build`. */
function coveredByDotNextSlash(dir: string): boolean {
  const normalized = normalizeDist(dir);
  return normalized === DEV_DIST || normalized.startsWith(`${DEV_DIST}/`);
}

function isGitIgnored(repoRelative: string): boolean {
  const result = spawnSync("git", ["check-ignore", "-q", "--", repoRelative], {
    cwd: REPO_ROOT,
    encoding: "utf8",
  });
  if (result.error) throw result.error;
  return result.status === 0;
}

async function namedBuildDists(): Promise<string[]> {
  const dirs = new Set<string>();
  const nextConfig = read(path.join(WEB_ROOT, "next.config.ts"));
  for (const dir of literalDistDirs(nextConfig)) dirs.add(dir);
  for (const dir of explicitBuildDists(nextConfig)) dirs.add(dir);
  for (const invocation of buildInvocations()) {
    for (const dir of explicitBuildDists(invocation.text)) dirs.add(dir);
    for (const dir of literalDistDirs(invocation.text)) dirs.add(dir);
  }
  const e2e = await loadDistDir(allEnv(webServerText()), PHASE_PRODUCTION_BUILD);
  if (e2e !== DEV_DIST) dirs.add(e2e);
  return [...dirs];
}

async function ignoredBuildDists(): Promise<string[]> {
  const missing: string[] = [];
  for (const dir of await namedBuildDists()) {
    for (const rel of [`apps/web/${dir}`, `apps/web/${dir}/BUILD_ID`]) {
      if (!isGitIgnored(rel)) missing.push(rel);
    }
  }
  return missing;
}

test("test_ac1_positive_scripts_set_build_dist_dir_outside_dot_next", async () => {
  const pkg = JSON.parse(read(path.join(WEB_ROOT, "package.json"))) as {
    scripts?: Record<string, string>;
  };
  const devScript = pkg.scripts?.dev ?? "";
  const failures: string[] = [];
  if (!devScript.includes("next dev")) failures.push("dev script does not run next dev");
  if (explicitBuildDists(devScript).length !== 0) {
    failures.push("dev script moves off .next");
  }
  const devDist = await loadDistDir(distEnv(devScript), PHASE_DEVELOPMENT_SERVER);
  if (devDist !== DEV_DIST) failures.push(`dev distDir is ${devDist}`);
  for (const invocation of buildInvocations()) {
    if (!(await scriptIsolates(invocation.text))) {
      failures.push(`${invocation.name} does not set its own distDir`);
    }
  }
  expect(failures, failures.join("; ")).toEqual([]);
});

test("test_ac1_negative_bare_build_or_remembered_flag_shares_dot_next", async () => {
  expect(await scriptIsolates("next build --turbopack")).toBe(false);
  expect(await scriptIsolates("PLAYWRIGHT_E2E_BUILD=1 pnpm exec next build")).toBe(false);
  const failures = [];
  for (const invocation of buildInvocations()) {
    if (!(await scriptIsolates(invocation.text))) failures.push(invocation.name);
  }
  expect(failures, failures.join(", ")).toEqual([]);
});

test("test_ac2_positive_playwright_and_every_build_script_set_dist_dir", async () => {
  const invocations = buildInvocations();
  const names = invocations.map((invocation) => invocation.name);
  expect(names).toContain("apps/web/package.json:build");
  expect(names).toContain("apps/web/playwright.config.ts:webServer");
  const failures: string[] = [];
  for (const invocation of invocations) {
    const dirs = explicitBuildDists(invocation.text);
    if (dirs.length === 0 || !(await scriptIsolates(invocation.text))) {
      failures.push(`${invocation.name} distDirs=${dirs.join("|") || "none"}`);
    }
  }
  expect(failures, failures.join("; ")).toEqual([]);
});

test("test_ac2_negative_flag_without_directory_is_not_explicit", async () => {
  const remembered = "PLAYWRIGHT_E2E_BUILD=1 pnpm exec next build && pnpm exec next start";
  expect(explicitBuildDists(remembered)).toEqual([]);
  expect(await scriptIsolates(remembered)).toBe(false);
  const failures: string[] = [];
  for (const invocation of buildInvocations()) {
    if (explicitBuildDists(invocation.text).length === 0) failures.push(invocation.name);
  }
  expect(failures, failures.join(", ")).toEqual([]);
});

test("test_ac3_positive_e2e_build_does_not_share_dev_dist_for_three_routes", async () => {
  const pkg = JSON.parse(read(path.join(WEB_ROOT, "package.json"))) as {
    scripts?: Record<string, string>;
  };
  const devDist = await loadDistDir(distEnv(pkg.scripts?.dev ?? ""), PHASE_DEVELOPMENT_SERVER);
  const e2eDist = await loadDistDir(allEnv(webServerText()), PHASE_PRODUCTION_BUILD);
  expect(
    holdsAc3(devDist, e2eDist),
    `dev=${devDist} e2e=${e2eDist} would replace chunks for ${DEV_ROUTES.join(" ")}`,
  ).toBe(true);
});

test("test_ac3_negative_shared_dot_next_is_a_missing_chunk_build", async () => {
  expect(holdsAc3(DEV_DIST, DEV_DIST)).toBe(false);
  const devDist = await loadDistDir({}, PHASE_DEVELOPMENT_SERVER);
  const e2eDist = await loadDistDir(allEnv(webServerText()), PHASE_PRODUCTION_BUILD);
  expect(
    holdsAc3(devDist, e2eDist),
    `e2e build dist ${e2eDist} shares dev dist and drops ${DEV_ROUTES.join(" ")}`,
  ).toBe(true);
});

test("test_ac4_positive_gitignore_covers_every_build_dist_dir", async () => {
  const dirs = await namedBuildDists();
  expect(dirs.length).toBeGreaterThan(0);
  const missing = await ignoredBuildDists();
  expect(missing, `unignored: ${missing.join(", ")}`).toEqual([]);
});

test("test_ac4_negative_dot_next_slash_misses_sibling_dist_dirs", async () => {
  expect(coveredByDotNextSlash(DEV_DIST)).toBe(true);
  expect(coveredByDotNextSlash(".next-e2e")).toBe(false);
  expect(coveredByDotNextSlash(".next-build")).toBe(false);
  const dirs = await namedBuildDists();
  expect(dirs.length).toBeGreaterThan(0);
  for (const dir of dirs) {
    expect(coveredByDotNextSlash(dir), dir).toBe(false);
  }
  const missing = await ignoredBuildDists();
  expect(missing, `unignored: ${missing.join(", ")}`).toEqual([]);
});
