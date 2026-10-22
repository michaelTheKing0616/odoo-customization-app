/**
 * UI-S-14 — replace bare string errors with what / why / next.
 * Copy follows playbook §9 (no em dashes, plain human language).
 */

export type WebsiteErrorParts = {
  what: string;
  why: string;
  next: string;
  /** Original message for Diagnose / details. */
  raw: string;
};

function clean(raw: string): string {
  return (raw || "").trim().replace(/\s+/g, " ");
}

/** Map a raw API / gate / network message into what / why / next. */
export function formatWebsiteError(raw: string): WebsiteErrorParts {
  const why = clean(raw) || "Something went wrong while editing the website page.";

  if (/Unsafe website|Unsafe QWeb|t-raw|t-out|external entities|javascript:|event handlers|allowlist|must not contain QWeb/i.test(why)) {
    return {
      what: "Save was blocked by the unsafe gate",
      why,
      next: "Remove script tags, t-raw, t-out, on* handlers, and javascript: URLs, then save again.",
      raw: why,
    };
  }

  if (/website module not|module not installed|not available/i.test(why)) {
    return {
      what: "The Website module is not available on this Odoo",
      why,
      next: "Install Website in Odoo Apps, then refresh the page list here.",
      raw: why,
    };
  }

  if (/Failed to load|could not load|load page/i.test(why)) {
    return {
      what: "This page could not be loaded",
      why,
      next: "Check the connection is online, then pick the page again from the list.",
      raw: why,
    };
  }

  if (/Publish failed|is_published|publish/i.test(why) && /fail|error|refused|denied|403|401|502/i.test(why)) {
    return {
      what: "Publish did not complete",
      why,
      next: "Confirm you can write website.page on this connection, then try Publish again.",
      raw: why,
    };
  }

  if (/Upload failed|upload|5MB|empty file|413/i.test(why)) {
    return {
      what: "Image upload did not complete",
      why,
      next: "Use an image under 5 MB, then try Replace image again.",
      raw: why,
    };
  }

  if (/Save failed|arch_db|ir\.ui\.view|write/i.test(why)) {
    return {
      what: "The page could not be saved",
      why,
      next: "Fix the issue above, then click Save page again.",
      raw: why,
    };
  }

  if (/network|fetch|Failed to fetch|timeout|502|503|ECONNREFUSED/i.test(why)) {
    return {
      what: "The connection to Ingenium or Odoo dropped",
      why,
      next: "Check the network and Odoo URL, then retry the same action.",
      raw: why,
    };
  }

  return {
    what: "Website editor could not finish that step",
    why,
    next: "Fix the issue above, then try again. Use Diagnose with Expert if it keeps failing.",
    raw: why,
  };
}
