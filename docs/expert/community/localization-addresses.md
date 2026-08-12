# Localization — States, Governorates, and Address Fields

Curated Expert knowledge (distilled from Odoo official docs, odoo/odoo `base` data, and
community forum patterns). Not a live forum scrape.

## How Odoo models states and governorates

Odoo stores regions in **`res.country.state`**, linked to **`res.country`** via `country_id`.
Partner and company address forms show a **State** dropdown when states exist for the selected
country.

- **Module:** mostly `base` (`odoo/addons/base/data/res.country.state.csv`) — not every country
  has preloaded states.
- **UI path:** Contacts → Configuration → Localization → **Fed. States** (or Settings →
  Countries / States depending on version and apps installed).
- **Custom regions:** import CSV or create records manually when Odoo does not ship your
  governorate name.

## Jordan — Capital Governorate vs Amman

**Question:** Is *Capital Governorate* represented as a State on Odoo for Jordan?

**Odoo 17.0–19.0:** Jordan (`jo`) has **12 governorates** preloaded in `res.country.state`
(from `base` data), including **Amman**, **Zarqa**, **Irbid**, **Aqaba**, **Balqa**, etc.
There is **no row named "Capital Governorate"** — Odoo uses the governorate name **Amman**
(`state_jo_am`, code `JO-AM`) for the capital region, not the administrative label
*Muḥāfaẓat al-ʿĀṣimah* / *Capital Governorate*.

**Odoo 16.0:** Jordan states are **not** preloaded in base — the State field stays empty until
you add states manually or upgrade to a version that ships them.

**Payroll / JoFotara docs** sometimes note that Jordanian company setup may leave **State**
blank in practice (postal code + city matter more for e-invoicing). That does not remove
`res.country.state` records — it reflects typical data entry.

**If you need "Capital Governorate" literally:** add a custom `res.country.state` for country
Jordan, or map your integration to **Amman**.

**Modules:** `l10n_jo` (accounting), `l10n_jo_edi` (JoFotara) — neither replaces base state
names.

## Kuwait — governorates

**Odoo 16–19:** Kuwait (`kw`) has **`l10n_kw`** (accounting/chart) but **no default
`res.country.state` rows** in base data for Kuwait in standard Community builds checked.
The **State** field on Kuwaiti addresses is typically **empty** unless you:

1. Create governorates manually in **Fed. States**, or
2. Import a CSV of `res.country.state` rows for `country_id` = Kuwait.

**Capital Governorate (Kuwait):** not shipped as a default state name — add **Capital** /
**Al Asimah** manually if your workflow requires it.

## United States and other countries

The US has full state lists in base. Many MENA countries have partial or no preloaded states.
Always verify on **your Odoo version** — state data is added in base across releases.

## Forum / community pattern (curated)

Common Odoo forum answer when states are missing:

> `res.country.state.csv` in base does not include every region for every country. Add states
> from the UI (**Contacts → Configuration → Localization → Fed. States**) or define/import CSV
> in your module, then upgrade/install.

For bulk address cleanup, use this app's **Bulk Suite** on `res.partner` when connected.

## Retrieval keywords

governorate, state, province, res.country.state, Fed. States, localization, l10n_jo, l10n_kw,
Jordan, Kuwait, Capital Governorate, Amman, address field, country states
