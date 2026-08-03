Developer Documentation
=========================

Views
-----

View inheritance lets you extend existing Odoo views without replacing them entirely.

Inheritance
~~~~~~~~~~~

Use ``xpath`` expressions to target nodes in the parent arch. The ``position``
attribute controls how the matched node is modified: ``inside``, ``after``,
``before``, ``replace``, or ``attributes``.

Example:

.. code-block:: xml

   <xpath expr="//field[@name='partner_id']" position="after">
       <field name="x_custom_ref"/>
   </xpath>

Field widgets
~~~~~~~~~~~~~

Widgets change how fields render in the UI. Common widgets include ``many2many_tags``,
``statusbar``, ``image``, and ``monetary``. Pick a widget compatible with the field type.

Smart buttons
-------------

Smart buttons appear in the button box on form views. They typically open related
records filtered to the current record.

Attributes
----------

The ``attrs`` / ``invisible`` / ``readonly`` / ``required`` modifiers control dynamic
field behavior based on other field values or user groups.

List views
----------

List (tree) views support optional columns, decorations, and editable rows. Use
``editable="bottom"`` for inline editing on new lines.

Search views
------------

Search views define filters and group-by options. Domain filters use standard Odoo
domain syntax.

Security
--------

Access rights and record rules govern who can read or write model data. Custom models
need explicit ``ir.model.access`` entries.

Testing views
-------------

Always validate inherited views in a sandbox before promoting to production. Broken
xpath targets raise install/upgrade errors.

Advanced inheritance patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When multiple modules inherit the same view, priority and module load order matter.
Lower-priority inherited views apply later; conflicting xpath targets may require
coordinated module dependencies.

Use ``//sheet`` or ``//form`` anchors sparingly — prefer stable field names. Document
your xpath choices in module README files for maintainers.

Studio parity note: Community customization uses the same ``ir.ui.view`` inheritance
mechanism as manual module development. Never copy Enterprise Studio source; use
public ORM/RPC and documented view XML only.

Performance considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Heavy ``invisible`` conditions on large list views can slow rendering. Prefer
computed stored fields or simplified domains when possible.

For kanban and graph views, limit the number of declared fields to those required for
display and drag-and-drop behavior.

Multi-company views
~~~~~~~~~~~~~~~~~~~

When a model is company-dependent, ensure related fields respect company context.
``company_id`` defaults and domain filters should align with record rules.

Localization
~~~~~~~~~~~~

Translated field labels use ``string`` on fields and ``_()`` in Python for model
descriptions. View-level ``string`` attributes override defaults per language when
exported through standard i18n files.

Migration checklist
~~~~~~~~~~~~~~~~~~~

Before upgrading Odoo major versions, diff inherited views against the new base arch.
Renamed fields and restructured templates are the most common breakage sources.

Run module update in sandbox, open affected forms and lists, and fix xpath before
production rollout.

Appendix: glossary
------------------

- **Arch**: XML definition of a view.
- **XPath**: Path expression selecting nodes in the arch.
- **Smart button**: Stat button opening a filtered action.
- **Domain**: Filter expression using Polish notation lists.

This appendix provides quick reference terms for developers new to Odoo view
customization. Cross-link to official documentation for version-specific API changes.

Extended reference section
~~~~~~~~~~~~~~~~~~~~~~~~~~

This section is intentionally verbose for chunker testing. It repeats concepts with
additional detail so automated tests can verify paragraph-boundary splitting and
continuation markers when a single subsection exceeds twice the maximum token target.

Paragraph one discusses inheritance mechanics, xpath stability, and module ordering.
Developers should treat inherited views as contracts between modules: changing a base
view in one addon may break dependents that assumed earlier structure.

Paragraph two covers widget selection, field type compatibility, and monetary fields
requiring a currency field or company currency default. Image fields may use ``image``
or ``image_url`` widgets depending on storage strategy.

Paragraph three explains search view domains, context keys passed to actions, and how
default filters appear in the UI. Group-by clauses must reference stored fields or
non-stored fields explicitly allowed by Odoo version capabilities.

Paragraph four documents security: access CSV rows, record rules with domain filters,
and implied groups from category hierarchies. Missing access rows produce ACL errors
that look like missing models to end users.

Paragraph five walks through testing: sandbox install, upgrade path, uninstall cleanup,
and snapshot rollback before risky metadata writes on production connections.

Paragraph six adds deployment guidance: export modules as zips, validate manifests,
declare dependencies explicitly, and avoid silent ``auto_install`` unless the module
truly applies universally.

Paragraph seven summarizes Studio parity constraints for Community: public RPC only,
no Enterprise source, snapshot before destructive mutations, and promote Python via
sandbox-tested modules rather than live ``state=code`` server actions.

Paragraph eight closes with maintenance tips: keep inheritance chains shallow, name
custom fields with ``x_`` prefix conventions, and document business rules in module
descriptions for consultants reviewing the implementation.

Paragraph nine reiterates version differences: dotted ``update_path`` and related write
behaviors vary by major version; consult the capability matrix before promising
features on older instances.

Paragraph ten provides a final checklist for code review: manifest order, data file
naming, security CSV completeness, demo data isolation, and report template validation.

Paragraph eleven discusses list view decorations using ``decoration-danger`` and
similar attributes tied to Python expressions evaluated client-side with safe context.

Paragraph twelve covers form view status bars, state fields, and workflow-style buttons
that trigger server actions or wizard launches through ``type="action"`` buttons.

Paragraph thirteen explains kanban stages, progress bars, and quick-create behavior on
many2one fields in kanban cards for mobile-friendly workflows.

Paragraph fourteen addresses calendar and gantt views when scheduling modules are
present, including all-day events and timezone handling for multi-region teams.

Paragraph fifteen finishes with links mindset: use ``ir.actions.act_window`` definitions
with clear names, domain filters referencing active_id, and target ``current`` vs
``new`` for modal workflows.

Paragraph sixteen adds notes on report QWeb templates: external layouts, paperformat
records, and print actions bound to model print menus.

Paragraph seventeen covers email templates and automated mail activities triggered from
automations, keeping template translations in sync with view strings.

Paragraph eighteen mentions portal and website snippets only at high level because
Expert RAG focuses on backend customization patterns for Community ERP deployments.

Paragraph nineteen discusses audit trails: mail.thread inheritance, tracking on fields,
and message_subtype configuration for chatter visibility.

Paragraph twenty closes the extended reference with encouragement to ingest official
version-tagged documentation and to decline answers when retrieval confidence is low.
