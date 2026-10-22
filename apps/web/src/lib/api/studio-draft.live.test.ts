// @vitest-environment node
/**
 * Live proof for decideStudioStockApp and startOptionABatch.
 * API_BASE is captured when the client module is first evaluated, so
 * NEXT_PUBLIC_API_URL is set before that import. The API listens on
 * 127.0.0.1:8099. The Odoo stand-in listens on 127.0.0.1 on another port.
 */
import { spawn, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, expect, it, vi } from "vitest";

process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:8099";

const API_PORT = 8099;
const FORBIDDEN_PORTS = new Set([
  3002, 8001, 8002, 8012, 5433, 5436, 11434, 8069, 8070, 8071, 8072, 8073,
]);

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../../..");
const pythonBin = path.join(repoRoot, ".venv/bin/python3");
const workDir = fs.mkdtempSync(path.join(os.tmpdir(), "ingenium_v_studiodraft_"));
const dbFile = path.join(workDir, "ingenium_v_studiodraft.db");
const httpLog = path.join(workDir, "http.jsonl");
const stubLog = path.join(workDir, "stub.jsonl");
const scriptPath = path.join(workDir, "harness.py");
const databaseUrl = `sqlite:///${dbFile}?check_same_thread=false&timeout=30`;

type Ready = {
  api_port: number;
  stub_port: number;
  decline_id: string;
  install_id: string;
  parent_id: string;
  child_id: string;
  db: string;
};

type HttpRow = {
  t: number;
  end: number;
  method: string;
  path: string;
  status: number;
  body: { decision?: string; dry_run?: boolean } | null;
};

type StubRow = { t: number; model: string; method: string };

let child: ChildProcess | undefined;
let ready: Ready;
let studioDraftApi: Awaited<ReturnType<typeof loadApi>>;

const HARNESS = String.raw`
import json
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xmlrpc.server import SimpleXMLRPCDispatcher

db_file = os.environ["STUDIO_DRAFT_DB"]
if not os.path.basename(db_file).startswith("ingenium_"):
    raise SystemExit("sqlite name must start with ingenium_")
database_url = os.environ["DATABASE_URL"]
if not database_url.startswith("sqlite:") or "5433" in database_url or "odoo_custom" in database_url:
    raise SystemExit("refusing non-disposable database")

os.environ["AUTH_MODE"] = "off"
os.environ["AI_ASSIST"] = "off"
os.environ["AI_RAG"] = "off"
os.environ["DB_MIGRATIONS"] = "off"
os.environ["INGENIUM_BUILDERS_TICKER"] = "0"

HTTP_LOG = os.environ["STUDIO_DRAFT_HTTP_LOG"]
STUB_LOG = os.environ["STUDIO_DRAFT_STUB_LOG"]
_log_lock = threading.Lock()
_sale_installed = False
FORBIDDEN = {3002, 8001, 8002, 8012, 5433, 5436, 11434, 8099} | set(range(8069, 8074))

def append_log(path, row):
    line = json.dumps(row) + "\n"
    with _log_lock:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)

def _terms(args):
    if not args or not isinstance(args[0], (list, tuple)):
        return []
    out = []
    for term in args[0]:
        if isinstance(term, (list, tuple)) and len(term) >= 3:
            out.append((term[0], term[1], term[2]))
    return out

def execute_kw(db, uid, password, model, method, args, kwargs=None):
    global _sale_installed
    del db, uid, password, kwargs
    append_log(STUB_LOG, {"t": time.time(), "model": model, "method": method})
    if model == "ir.module.module" and method == "button_immediate_install":
        _sale_installed = True
        return True
    if model == "ir.module.module" and method == "search_read":
        name = state = None
        for field, op, value in _terms(args or []):
            if field == "name" and op == "=":
                name = value
            if field == "state" and op == "=":
                state = value
        current = "installed" if _sale_installed else "uninstalled"
        if name not in (None, "sale"):
            return []
        if state not in (None, current):
            return []
        if name is None and state is None:
            return []
        return [{"id": 42, "name": "sale", "state": current}]
    if model == "ir.model" and method == "search_count":
        return 1
    if method == "fields_get":
        return {}
    if method in {"search", "search_read", "read", "name_search"}:
        return []
    if method == "search_count":
        return 0
    return False

COMMON = SimpleXMLRPCDispatcher(allow_none=True)
OBJECT = SimpleXMLRPCDispatcher(allow_none=True)

def version():
    return {"server_version": "19.0", "server_serie": "19.0", "protocol_version": 1}

def authenticate(db, user, password, context):
    del db, user, password, context
    return 2

COMMON.register_function(version, "version")
COMMON.register_function(authenticate, "authenticate")
OBJECT.register_function(execute_kw, "execute_kw")

class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        data = self.rfile.read(length)
        path = self.path.split("?", 1)[0]
        dispatcher = OBJECT if path.rstrip("/").endswith("/object") else COMMON
        response = dispatcher._marshaled_dispatch(data)
        raw = response.encode("utf-8") if isinstance(response, str) else response
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        return

def bind_stub():
    for _ in range(8):
        server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        port = int(server.server_address[1])
        if port not in FORBIDDEN:
            return server, port
        server.server_close()
    raise SystemExit("stub port landed on a forbidden port")

stub, stub_port = bind_stub()
threading.Thread(target=stub.serve_forever, name="odoo-stub", daemon=True).start()
stub_url = "http://127.0.0.1:%s" % stub_port
os.environ["ODOO_URL"] = stub_url
os.environ["ODOO_DB"] = "ingenium_stub"
os.environ["ODOO_USER"] = "stub"
os.environ["ODOO_PASSWORD"] = "stub"

from cryptography.fernet import Fernet

os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

class BodyLog:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        messages = []
        body = b""
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            body += message.get("body") or b""
            if not message.get("more_body", False):
                break
        started = time.time()
        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
        index = 0

        async def replay():
            nonlocal index
            if index < len(messages):
                item = messages[index]
                index += 1
                return item
            return {"type": "http.disconnect"}

        status = {"code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = int(message["status"])
            await send(message)

        await self.app(scope, replay, send_wrapper)
        append_log(HTTP_LOG, {
            "t": started,
            "end": time.time(),
            "method": scope.get("method"),
            "path": scope.get("path") or "",
            "status": status["code"],
            "body": parsed,
        })

def seed():
    from app.ai_conversation.session_store import create_session, update_session
    from app.crypto import encrypt_secret
    from app.db import SessionLocal, init_db
    from app.db_models import OdooConnection
    import uuid

    init_db()
    db = SessionLocal()
    try:
        conn_id = str(uuid.uuid4())
        db.add(OdooConnection(
            id=conn_id,
            name="ingenium disposable stub",
            url=stub_url,
            db_name="ingenium_stub",
            username="stub",
            secret_encrypted=encrypt_secret("stub"),
            server_version="19.0",
            hosting="self_hosted",
            write_mode="standard",
            writes_paused=False,
        ))
        db.commit()
        proposal = {
            "module": "sale",
            "app_label": "Sales",
            "model": "sale.order",
            "noun": "quotations",
            "installable": True,
            "question": "Install Sales to continue?",
            "reason": "Sales is not installed.",
            "install_label": "Install Sales and continue",
            "decline_label": "Not now",
        }
        clarification = {
            "id": "stock_app_install:sale",
            "kind": "stock_app_install",
            "merge_key": "stock_app_install",
            "question": proposal["question"],
            "help": proposal["reason"],
            "options": [
                {"id": "install", "label": proposal["install_label"]},
                {"id": "decline", "label": proposal["decline_label"]},
            ],
            "default_id": "decline",
            "stock_app": proposal,
        }
        prompt = "Add a note on quotations"
        decline = create_session(db, connection_id=None, feature="studio", prompt=prompt, status="clarifying")
        update_session(db, decline, pending_clarification=dict(clarification))
        install = create_session(db, connection_id=conn_id, feature="studio", prompt=prompt, status="clarifying")
        update_session(db, install, pending_clarification=dict(clarification))
        child = create_session(
            db, connection_id=None, feature="studio", prompt="Custom-code module", status="review",
        )
        parent = create_session(
            db, connection_id=None, feature="studio", prompt="Parent app with Python pieces", status="review",
        )
        piece = {
            "label": "Compute margin",
            "key": "compute_margin",
            "models": ["sale.order"],
            "reason": "Margin is not a stored field.",
            "delivery_lane": "module_sh_or_self",
            "online_blocked": False,
            "lane_note": "Custom Python needs one module.",
        }
        promote = {"mode": "single_button", "label": "Promote", "config_required": False}
        update_session(db, parent, artifact={
            "_option_a_batch": {
                "session_id": child.id,
                "pieces": [piece],
                "promote": promote,
                "draft": {"technical_name": "sale_logic", "_user_prompt": "Custom-code module"},
                "online_blocked": False,
                "status": "ready_to_author",
            }
        })
        return {
            "decline_id": decline.id,
            "install_id": install.id,
            "parent_id": parent.id,
            "child_id": child.id,
        }
    finally:
        db.close()

try:
    ids = seed()
except Exception:
    traceback.print_exc()
    raise SystemExit(1)

from app.main import app as fastapi_app

wrapped = BodyLog(fastapi_app)
payload = {
    "api_port": 8099,
    "stub_port": stub_port,
    "db": db_file,
    **ids,
}

def announce():
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8099/health", timeout=1) as resp:
                body = json.loads(resp.read().decode())
            if body.get("status") == "ok":
                print("READY " + json.dumps(payload), flush=True)
                return
        except Exception:
            time.sleep(0.15)
    print("FAILED health on 8099", flush=True)
    os._exit(1)

probe = socket.socket()
try:
    probe.bind(("127.0.0.1", 8099))
finally:
    probe.close()

threading.Thread(target=announce, name="ready", daemon=True).start()
import uvicorn
uvicorn.run(wrapped, host="127.0.0.1", port=8099, log_level="warning")
`;

function readJsonLines<T>(file: string): T[] {
  if (!fs.existsSync(file)) return [];
  return fs
    .readFileSync(file, "utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as T);
}

function waitForReady(proc: ChildProcess): Promise<Ready> {
  return new Promise((resolve, reject) => {
    let out = "";
    let err = "";
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new Error(`API did not become ready\n${out.slice(-1500)}\n${err.slice(-2500)}`));
    }, 150_000);
    proc.stdout?.setEncoding("utf8");
    proc.stderr?.setEncoding("utf8");
    proc.stdout?.on("data", (chunk: string) => {
      out += chunk;
      const line = out.split("\n").find((row) => row.startsWith("READY "));
      if (!line || settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(JSON.parse(line.slice("READY ".length)) as Ready);
    });
    proc.stderr?.on("data", (chunk: string) => {
      err += chunk;
    });
    proc.on("exit", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(`API exited ${code}\n${out.slice(-1500)}\n${err.slice(-2500)}`));
    });
  });
}

async function stopChild(proc: ChildProcess | undefined): Promise<void> {
  if (!proc || proc.exitCode != null || proc.pid == null) return;
  proc.kill("SIGTERM");
  const exited = await new Promise<boolean>((resolve) => {
    const timer = setTimeout(() => resolve(false), 5_000);
    proc.once("exit", () => {
      clearTimeout(timer);
      resolve(true);
    });
  });
  if (!exited && proc.exitCode == null) proc.kill("SIGKILL");
}

async function loadApi() {
  process.env.NEXT_PUBLIC_API_URL = "http://127.0.0.1:8099";
  vi.resetModules();
  const clientMod = await import("./client");
  if (clientMod.API_BASE !== "http://127.0.0.1:8099" || clientMod.getApiBase() !== "http://127.0.0.1:8099") {
    throw new Error(`API base is ${clientMod.getApiBase()} (API_BASE=${clientMod.API_BASE})`);
  }
  const apiMod = await import("./studio-draft");
  return apiMod.studioDraftApi;
}

beforeAll(async () => {
  if (!fs.existsSync(pythonBin)) throw new Error(`missing python ${pythonBin}`);
  if (!path.basename(dbFile).startsWith("ingenium_")) throw new Error("sqlite name");
  if (databaseUrl.includes("5433") || databaseUrl.includes("odoo_custom")) {
    throw new Error("refusing non-disposable database");
  }
  fs.writeFileSync(scriptPath, HARNESS);
  fs.writeFileSync(httpLog, "");
  fs.writeFileSync(stubLog, "");
  child = spawn(pythonBin, [scriptPath], {
    cwd: path.join(repoRoot, "apps/api"),
    env: {
      ...process.env,
      PYTHONPATH: [path.join(repoRoot, "apps/api"), process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
      PYTHONUNBUFFERED: "1",
      DATABASE_URL: databaseUrl,
      STUDIO_DRAFT_DB: dbFile,
      STUDIO_DRAFT_HTTP_LOG: httpLog,
      STUDIO_DRAFT_STUB_LOG: stubLog,
      AUTH_MODE: "off",
      AI_ASSIST: "off",
      AI_RAG: "off",
      DB_MIGRATIONS: "off",
      INGENIUM_BUILDERS_TICKER: "0",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  ready = await waitForReady(child);
  if (ready.api_port !== API_PORT) throw new Error(`api port ${ready.api_port}`);
  if (FORBIDDEN_PORTS.has(ready.stub_port) || ready.stub_port === API_PORT) {
    throw new Error(`stub port ${ready.stub_port}`);
  }
  if (!ready.db.endsWith("ingenium_v_studiodraft.db")) throw new Error(ready.db);
  studioDraftApi = await loadApi();
}, 180_000);

afterAll(async () => {
  await stopChild(child);
  fs.rmSync(workDir, { recursive: true, force: true });
}, 20_000);

function posts(sessionId: string, suffix: string): HttpRow[] {
  return readJsonLines<HttpRow>(httpLog).filter(
    (row) => row.method === "POST" && row.path.includes(`/sessions/${sessionId}/${suffix}`),
  );
}

it("startOptionABatch returns the existing child and the route shape", async () => {
  const out = await studioDraftApi.startOptionABatch(ready.parent_id);
  expect(Object.keys(out).sort()).toEqual(["pieces", "promote", "session_id"]);
  expect(typeof out.session_id).toBe("string");
  expect(out.session_id).toBe(ready.child_id);
  expect(Array.isArray(out.pieces)).toBe(true);
  expect(out.pieces).toHaveLength(1);
  const piece = out.pieces[0];
  if (!piece) throw new Error("missing piece");
  expect(Object.keys(piece).sort()).toEqual([
    "delivery_lane",
    "key",
    "label",
    "lane_note",
    "models",
    "online_blocked",
    "reason",
  ]);
  expect(typeof piece.label).toBe("string");
  expect(piece.label).toBe("Compute margin");
  expect(typeof piece.key).toBe("string");
  expect(piece.key).toBe("compute_margin");
  expect(Array.isArray(piece.models)).toBe(true);
  expect(piece.models).toEqual(["sale.order"]);
  expect(typeof piece.reason).toBe("string");
  expect(typeof piece.delivery_lane).toBe("string");
  expect(piece.delivery_lane).toBe("module_sh_or_self");
  expect(typeof piece.online_blocked).toBe("boolean");
  expect(piece.online_blocked).toBe(false);
  expect(typeof piece.lane_note).toBe("string");
  expect(Object.keys(out.promote).sort()).toEqual(["config_required", "label", "mode"]);
  expect(typeof out.promote.mode).toBe("string");
  expect(out.promote.mode).toBe("single_button");
  expect(typeof out.promote.label).toBe("string");
  expect(out.promote.label).toBe("Promote");
  expect(typeof out.promote.config_required).toBe("boolean");
  expect(out.promote.config_required).toBe(false);

  const parent = await studioDraftApi.getStudioSession(ready.parent_id);
  const stored = parent.artifact?._option_a_batch;
  if (!stored || typeof stored !== "object" || Array.isArray(stored)) {
    throw new Error("parent batch missing");
  }
  const batch = stored as { session_id?: unknown; status?: unknown };
  expect(batch.session_id).toBe(ready.child_id);
  expect(batch.status).toBe("ready_to_author");
  expect(posts(ready.parent_id, "option-a-batch")).toHaveLength(1);
}, 60_000);

it("decideStudioStockApp decline is one POST and returns the stopped session", async () => {
  const out = await studioDraftApi.decideStudioStockApp(ready.decline_id, "decline");
  const rows = posts(ready.decline_id, "stock-app");
  expect(rows).toHaveLength(1);
  expect(rows[0]?.status).toBe(200);
  expect(rows[0]?.body).toEqual({ decision: "decline", dry_run: false });
  expect(out.stopped).toBe(true);
  expect(out.status).toBe("stopped");
  expect(typeof out.message).toBe("string");
  expect(out.clarification ?? null).toBeNull();
}, 60_000);

it("decideStudioStockApp install previews, then sends the real POST", async () => {
  const out = await studioDraftApi.decideStudioStockApp(ready.install_id, "install");
  const rows = posts(ready.install_id, "stock-app");
  if (rows.length !== 2) {
    throw new Error(`install posts ${JSON.stringify(rows)}`);
  }
  expect(rows[0]?.body).toEqual({ decision: "install", dry_run: true });
  expect(rows[1]?.body).toEqual({ decision: "install", dry_run: false });
  expect(rows[0]?.status).toBe(200);
  expect(rows[1]?.status).toBe(200);
  expect(rows[0] && rows[1] && rows[0].end < rows[1].t).toBe(true);
  const stub = readJsonLines<StubRow>(stubLog);
  const previewEnd = rows[0].end;
  expect(stub.length).toBeGreaterThan(0);
  expect(stub.every((row) => row.t > previewEnd)).toBe(true);
  expect(stub.some((row) => row.model === "ir.module.module" && row.method === "button_immediate_install")).toBe(
    true,
  );
  expect(out.installed?.module).toBe("sale");
  expect(typeof out.installed?.app_label).toBe("string");
  expect(typeof out.installed?.message).toBe("string");
  expect(out.stopped).not.toBe(true);
}, 120_000);
