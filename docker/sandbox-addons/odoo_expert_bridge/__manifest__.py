# -*- coding: utf-8 -*-
{
    "name": "Odoo Expert Bridge",
    "version": "19.0.1.0.2",
    "category": "Productivity",
    "summary": "Open the No-Code Customization Expert from inside Odoo",
    "description": "Deep-link to the external Customization app Expert panel. Optional record context for chatter notes.",
    "author": "Odoo Customization Platform",
    "website": "https://github.com",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": ["views/expert_actions.xml"],
    "installable": True,
    "application": True,
    "sequence": 16,
}
