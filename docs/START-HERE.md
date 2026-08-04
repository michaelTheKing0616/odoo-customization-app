# Start here — try Odoo Custom on your machine

This guide is written for **you**, not for developers. No jargon where we can help it.

Odoo Custom is a website that sits beside your Odoo system. You use it to add fields, change screens, set up automations, and export customizations — **without** Odoo Enterprise Studio.

There is a longer reference, [USER-GUIDE.md](USER-GUIDE.md), with every screen explained. **This page** tells you how to turn everything on and what to click first.

---

## What’s running right now (for testing)

If someone on your team (or an assistant) just started the stack for you, open these in your browser:

| What | Address | Login |
|------|---------|--------|
| **Odoo Custom (the app)** | [http://127.0.0.1:3002](http://127.0.0.1:3002) | No login needed locally |
| **Odoo itself** | [http://127.0.0.1:8069](http://127.0.0.1:8069) | Email `admin` / password `admin` |
| **Optional: Docker build of the app** | [http://127.0.0.1:3000](http://127.0.0.1:3000) | May ask for an API key (see below) |

Keep **two tabs** open while you explore: Odoo Custom in one, Odoo in the other. Many actions only make sense when you can flip between “I changed something here” and “I see it there.”

---

## How to start everything yourself (first time)

You only do the heavy setup once. After that, starting the app is usually two commands.

### Step 1 — Start Odoo and the database (Docker)

Open Terminal, go to the project folder, and run:

```bash
cd ~/Odoo_Customization_App
docker compose -f docker/docker-compose.yml up -d
./docker/wait-for-odoo.sh
```

The first time on a fresh machine, also run:

```bash
./docker/init-db.sh
```

That creates a practice database called `odoo_dev` with username and password both set to `admin`.

**Check:** open [http://127.0.0.1:8069](http://127.0.0.1:8069) and log in as `admin` / `admin`.

### Step 2 — Start the backend (the “brain” of Odoo Custom)

In the same project folder:

```bash
uv sync
cp -n .env.example .env
```

Open a **new** Terminal window and run:

```bash
cd ~/Odoo_Customization_App/apps/api
AUTH_MODE=off uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Leave that window open.

**Check:** visit [http://127.0.0.1:8001/health](http://127.0.0.1:8001/health) — you should see `"status":"ok"` and `"database_ok":true`.

### Step 3 — Start the website (what you actually click)

Open another Terminal window:

```bash
cd ~/Odoo_Customization_App
pnpm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001 pnpm --filter @odoo-custom/web dev -H 127.0.0.1 -p 3002
```

**Check:** open [http://127.0.0.1:3002](http://127.0.0.1:3002) — you should see the Odoo Custom home page with a **Connect your Odoo** button.

### Stopping things

- In each Terminal window where the API or website is running: press `Ctrl+C`.
- To stop Odoo Docker: `docker compose -f docker/docker-compose.yml down` (from the project folder).

---

## Your first five minutes in the app

1. Go to [http://127.0.0.1:3002/connect](http://127.0.0.1:3002/connect).
2. Create a connection:
   - **Name:** anything you like, e.g. `My local Odoo`
   - **URL:** `http://127.0.0.1:8069`
   - **Database:** `odoo_dev`
   - **Username / password:** `admin` / `admin`
3. Save and open the connection. You should see models and menus load without errors.
4. In Odoo ([8069](http://127.0.0.1:8069)), stay logged in as admin — you’ll need that for “Open in Odoo” links.
5. From the connection sidebar, try **View Designer** or **App Wizard** (Draft Studio) when you’re ready to build something.

---

## What the product can do (in plain language)

Think of three buckets: **Build**, **Operate**, and **Stay safe**.

### Build — shape how Odoo looks and behaves

- **Models & Fields** — Add new types of records (like “Library Book”) or extra columns on existing ones (like a “Priority” field on contacts).
- **View Designer** — Change forms and lists: hide a field, move things around, add buttons, polish layouts. Changes can apply live or export as a module.
- **Menus** — Add or rearrange where things appear in Odoo’s app menu.
- **Automations** — “When a record is created or updated, do X” (send email, create activity, update another field, etc.).
- **Access** — Who can see or edit which records (groups and rules).
- **Reports** — Design or extend printed/PDF reports.
- **Approvals** — Multi-step sign-off flows on records.
- **Website** — Edit website pages (when the Website app is installed in Odoo).
- **Code Studio** — For advanced users: write small Python snippets, test them, bind them to buttons or automations (with confirmations and snapshots).
- **Draft Studio / ModuleSpec / Projects** — AI-assisted drafting of apps and specs; review before anything touches Odoo.
- **Odoo Expert** — Ask questions; answers are grounded in official Odoo documentation with citations.

### Operate — work on lots of data at once

- **Import** — Bring CSV/Excel data into Odoo carefully, with previews.
- **Bulk Suite** — Mass updates, deduplication, transitions, group changes — with dry-run previews when safety rules require them.
- **Power Ops** — Shortcut recipes for common admin tasks (export, cleanup, etc.).
- **Cron Manager** — See and manage scheduled jobs in Odoo.
- **Housekeeping** — Find stale or orphaned metadata and clean up safely.
- **Reminders** — Email templates and scheduled nudges tied to your data.
- **Script Runner** — Run one-off Python scripts against the connection (journaled, with guardrails).

### Govern — trust, undo, and configuration

- **Snapshots & Journal** — Before risky changes, the app often saves a restore point. The journal shows what changed and whether you can roll back.
- **Config** — Sequences, system parameters, and related settings exposed in one place.
- **Write modes** — Start in read-only “observer” mode; unlock “standard” or “production” write when you’re ready (with extra checks in production).
- **First-write interstitial** — The first time you change something on a connection, you’ll get a clear heads-up about what “live” means.

---

## A simple workflow most people follow

1. **Connect** your Odoo database.
2. **Build** something small — one field, one form tweak, or use the **Wizard** to scaffold a demo app (Library is a good first try).
3. **Check in Odoo** — open the model or menu and confirm it looks right.
4. **Export** (from the connection hub) if you want a portable module zip.
5. **Sandbox test** the zip before installing anywhere important.
6. **Promote** to another environment only after sandbox passes.

You don’t have to do all six steps on day one. Connecting and changing one field is a valid first win.

---

## When the app asks you to type a phrase

For actions that can hurt real data (installing modules, bulk deletes, overwriting views, etc.), you’ll see a confirmation box. Type exactly:

```text
I understand the risks
```

That’s on purpose. ERP systems hold business-critical data; the app wants you to pause once.

---

## If something doesn’t load

| Symptom | What to try |
|---------|-------------|
| Odoo Custom page is blank or “can’t connect” | Make sure the API terminal is still running (`8001/health` should be ok). |
| Browser console shows **Failed to fetch** on `/connect` | API CORS must include your web origin. Restart the API after updating `CORS_ORIGINS` in `.env` (defaults now include `:3002`). |
| “Unauthorized” or API errors on `:3000` | Use [http://127.0.0.1:3002](http://127.0.0.1:3002) instead, or add an API key under **Settings**. |
| Odoo login fails | Database might not exist — run `./docker/init-db.sh` once. |
| New menu doesn’t appear in Odoo | Log out and back into Odoo, or clear menu cache (see [USER-GUIDE.md](USER-GUIDE.md) troubleshooting). |
| Docker says port already in use | Something else is using 8069 or 3000 — stop old containers or pick another port. |

More detail: [LOCAL-UAT.md](LOCAL-UAT.md) (checklist for testers) and [USER-GUIDE.md](USER-GUIDE.md) (full product manual).

---

## Where to go next

- **Full screen-by-screen manual:** [USER-GUIDE.md](USER-GUIDE.md)
- **Step-by-step test checklist:** [LOCAL-UAT.md](LOCAL-UAT.md)
- **Safety and trust features:** [SAFETY.md](SAFETY.md)
- **Deploying for real users:** [DEPLOY.md](DEPLOY.md)

Happy customizing — and when in doubt, make a snapshot before you click the scary button.
