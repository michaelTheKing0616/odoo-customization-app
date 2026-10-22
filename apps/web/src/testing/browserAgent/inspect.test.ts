import { describe, expect, it } from "vitest";

import { inspectModuleFiles } from "./inspect.mjs";

const MODULE = "x_ticket_browser";

const CLEAN = {
  [`${MODULE}/__manifest__.py`]: "{'name': 'Tickets', 'version': '1.0'}\n",
  [`${MODULE}/views/ticket_views.xml`]: `<?xml version='1.0' encoding='utf-8'?>
<odoo>
  <record id="view_x_ticket_form" model="ir.ui.view">
    <field name="name">x.ticket.form</field>
    <field name="model">x_ticket</field>
    <field name="arch" type="xml">
      <form string="Ticket">
        <sheet><group><field name="name"/></group></sheet>
      </form>
    </field>
  </record>
</odoo>
`,
};

const DIRTY = {
  ...CLEAN,
  [`${MODULE}/views/ticket_views.xml`]: `<?xml version='1.0' encoding='utf-8'?>
<odoo>
  <record id="view_x_ticket_form" model="ir.ui.view">
    <field name="name">x.ticket.form</field>
    <field name="model">x_ticket</field>
    <field name="arch" type="xml">
      <form string="Ticket">
        <sheet><group><field name="name">
      </form>
    </field>
  </record>
</odoo>
`,
};

describe("browserAgent inspect", () => {
  it("catches unparseable ir.ui.view arch", () => {
    const report = inspectModuleFiles(DIRTY);
    expect(report.ok).toBe(false);
    expect(report.caught[0]).toMatchObject({
      module: MODULE,
      defect: "view_arch_unparseable",
    });
  });

  it("does not report that defect on a clean form", () => {
    const report = inspectModuleFiles(CLEAN);
    expect(report.ok).toBe(true);
    expect(report.views_checked).toBe(1);
    expect(report.caught).toEqual([]);
    expect(report.false_positive_rate).toBe(0);
  });
});
