"""Curated ModuleSpec packs for robust NL drafts when the LLM is thin or offline.

Public ORM/RPC shapes only — no Studio Enterprise. Packs are merged into drafts
after Ollama (or used alone when AI is off and the prompt matches).
"""

from __future__ import annotations

import copy
import re
from typing import Any


def _sel(*pairs: tuple[str, str]) -> str:
    inner = ", ".join(f"('{k}', '{v}')" for k, v in pairs)
    return f"[{inner}]"


def car_rental_pack() -> dict[str, Any]:
    """Serious car-rental ops ModuleSpec (fleet, customers, contracts, pricing, …)."""
    vehicle_status = _sel(
        ("available", "Available"),
        ("rented", "Rented"),
        ("maintenance", "Maintenance"),
        ("retired", "Retired"),
    )
    contract_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("active", "Active"),
        ("returned", "Returned"),
        ("cancelled", "Cancelled"),
        ("overdue", "Overdue"),
    )
    category_sel = _sel(
        ("economy", "Economy"),
        ("compact", "Compact"),
        ("suv", "SUV"),
        ("van", "Van"),
        ("luxury", "Luxury"),
    )
    damage_status = _sel(
        ("reported", "Reported"),
        ("assessed", "Assessed"),
        ("repaired", "Repaired"),
        ("waived", "Waived"),
    )
    maint_status = _sel(
        ("planned", "Planned"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    pay_status = _sel(
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )

    return {
        "technical_name": "car_rental",
        "display_name": "Car Rental",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "car_rental",
        "models": [
            {
                "model": "x_rent_branch",
                "description": "Branch / Location",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Branch Name", "required": True},
                    {"name": "x_code", "ttype": "char", "string": "Code"},
                    {"name": "x_address", "ttype": "char", "string": "Address"},
                    {"name": "x_phone", "ttype": "char", "string": "Phone"},
                ],
            },
            {
                "model": "x_rent_vehicle",
                "description": "Vehicle",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Display Name", "required": True},
                    {"name": "x_make", "ttype": "char", "string": "Make", "required": True},
                    {"name": "x_model", "ttype": "char", "string": "Model", "required": True},
                    {"name": "x_year", "ttype": "integer", "string": "Year"},
                    {"name": "x_plate", "ttype": "char", "string": "License Plate", "required": True},
                    {"name": "x_vin", "ttype": "char", "string": "VIN"},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": vehicle_status,
                        "required": True,
                    },
                    {
                        "name": "x_category",
                        "ttype": "selection",
                        "string": "Category",
                        "selection": category_sel,
                    },
                    {
                        "name": "x_branch_id",
                        "ttype": "many2one",
                        "string": "Branch",
                        "relation": "x_rent_branch",
                    },
                    {"name": "x_odometer", "ttype": "integer", "string": "Odometer"},
                    {"name": "x_color", "ttype": "char", "string": "Color"},
                    {
                        "name": "x_contract_ids",
                        "ttype": "one2many",
                        "string": "Rentals",
                        "relation": "x_rent_contract",
                        "relation_field": "x_vehicle_id",
                    },
                ],
            },
            {
                "model": "x_rent_customer",
                "description": "Rental Customer",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {"name": "x_license_number", "ttype": "char", "string": "Driver License"},
                    {"name": "x_license_expiry", "ttype": "date", "string": "License Expiry"},
                    {"name": "x_license_country", "ttype": "char", "string": "License Country"},
                    {
                        "name": "x_documents",
                        "ttype": "binary",
                        "string": "Documents",
                        "help": "Upload ID / license scans (stub)",
                    },
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
            {
                "model": "x_rent_rate",
                "description": "Rental Rate",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Rate Name", "required": True},
                    {
                        "name": "x_category",
                        "ttype": "selection",
                        "string": "Vehicle Category",
                        "selection": category_sel,
                    },
                    {"name": "x_daily_rate", "ttype": "float", "string": "Daily Rate"},
                    {"name": "x_weekly_rate", "ttype": "float", "string": "Weekly Rate"},
                    {"name": "x_deposit", "ttype": "float", "string": "Default Deposit"},
                    {"name": "x_mileage_limit", "ttype": "integer", "string": "Daily Mileage Limit"},
                    {"name": "x_extra_km_rate", "ttype": "float", "string": "Extra KM Rate"},
                    {"name": "x_tax_percent", "ttype": "float", "string": "Tax %"},
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": "x_rent_extra",
                "description": "Extra / Add-on",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Extra Name", "required": True},
                    {"name": "x_daily_price", "ttype": "float", "string": "Daily Price"},
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": "x_rent_contract",
                "description": "Rental Contract",
                "mode": "new",
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Reference", "required": True},
                    {
                        "name": "x_customer_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "x_rent_customer",
                        "required": True,
                    },
                    {
                        "name": "x_vehicle_id",
                        "ttype": "many2one",
                        "string": "Vehicle",
                        "relation": "x_rent_vehicle",
                        "required": True,
                    },
                    {
                        "name": "x_rate_id",
                        "ttype": "many2one",
                        "string": "Rate Plan",
                        "relation": "x_rent_rate",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": contract_status,
                        "required": True,
                    },
                    {"name": "x_pickup_datetime", "ttype": "datetime", "string": "Pickup"},
                    {"name": "x_return_datetime", "ttype": "datetime", "string": "Return Due"},
                    {"name": "x_actual_return", "ttype": "datetime", "string": "Actual Return"},
                    {
                        "name": "x_pickup_branch_id",
                        "ttype": "many2one",
                        "string": "Pickup Branch",
                        "relation": "x_rent_branch",
                    },
                    {
                        "name": "x_return_branch_id",
                        "ttype": "many2one",
                        "string": "Return Branch",
                        "relation": "x_rent_branch",
                    },
                    {"name": "x_daily_rate", "ttype": "float", "string": "Daily Rate"},
                    {"name": "x_deposit", "ttype": "float", "string": "Deposit"},
                    {"name": "x_insurance", "ttype": "boolean", "string": "Insurance"},
                    {"name": "x_insurance_fee", "ttype": "float", "string": "Insurance Fee"},
                    {"name": "x_mileage_limit", "ttype": "integer", "string": "Mileage Limit"},
                    {"name": "x_odometer_out", "ttype": "integer", "string": "Odometer Out"},
                    {"name": "x_odometer_in", "ttype": "integer", "string": "Odometer In"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                    {
                        "name": "x_payment_ids",
                        "ttype": "one2many",
                        "string": "Payments",
                        "relation": "x_rent_payment",
                        "relation_field": "x_contract_id",
                    },
                    {
                        "name": "x_damage_ids",
                        "ttype": "one2many",
                        "string": "Damages",
                        "relation": "x_rent_damage",
                        "relation_field": "x_contract_id",
                    },
                ],
            },
            {
                "model": "x_rent_payment",
                "description": "Rental Payment (stub)",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Label", "required": True},
                    {
                        "name": "x_contract_id",
                        "ttype": "many2one",
                        "string": "Contract",
                        "relation": "x_rent_contract",
                        "required": True,
                    },
                    {"name": "x_amount", "ttype": "float", "string": "Amount", "required": True},
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": pay_status,
                    },
                    {"name": "x_date", "ttype": "date", "string": "Date"},
                    {
                        "name": "x_notes",
                        "ttype": "text",
                        "string": "Notes",
                        "help": "Stub until accounting (account.move) link",
                    },
                ],
            },
            {
                "model": "x_rent_damage",
                "description": "Damage Report",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {
                        "name": "x_contract_id",
                        "ttype": "many2one",
                        "string": "Contract",
                        "relation": "x_rent_contract",
                    },
                    {
                        "name": "x_vehicle_id",
                        "ttype": "many2one",
                        "string": "Vehicle",
                        "relation": "x_rent_vehicle",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": damage_status,
                    },
                    {"name": "x_description", "ttype": "text", "string": "Description"},
                    {"name": "x_cost", "ttype": "float", "string": "Estimated Cost"},
                    {"name": "x_reported_date", "ttype": "date", "string": "Reported"},
                ],
            },
            {
                "model": "x_rent_maintenance",
                "description": "Maintenance",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {
                        "name": "x_vehicle_id",
                        "ttype": "many2one",
                        "string": "Vehicle",
                        "relation": "x_rent_vehicle",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": maint_status,
                    },
                    {"name": "x_scheduled_date", "ttype": "date", "string": "Scheduled"},
                    {"name": "x_completed_date", "ttype": "date", "string": "Completed"},
                    {"name": "x_odometer", "ttype": "integer", "string": "Odometer"},
                    {"name": "x_cost", "ttype": "float", "string": "Cost"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_rent_vehicle",
                "label": "Rentals",
                "related_model": "x_rent_contract",
                "relation_field": "x_vehicle_id",
                "one2many_field": "x_contract_ids",
                "icon": "fa-car",
            },
            {
                "on_model": "x_rent_contract",
                "label": "Payments",
                "related_model": "x_rent_payment",
                "relation_field": "x_contract_id",
                "one2many_field": "x_payment_ids",
                "icon": "fa-money",
            },
            {
                "on_model": "x_rent_contract",
                "label": "Damages",
                "related_model": "x_rent_damage",
                "relation_field": "x_contract_id",
                "one2many_field": "x_damage_ids",
                "icon": "fa-wrench",
            },
        ],
        "automations": [
            {
                "name": "Mark vehicle rented on confirm",
                "model": "x_rent_contract",
                "trigger": "on_create_or_write",
                "description": "When contract becomes confirmed/active, set vehicle status to rented.",
                "filter_domain": "[('x_status', 'in', ['confirmed', 'active'])]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_vehicle_id",
                        "field": "x_status",
                        "value": "rented",
                    }
                ],
            },
            {
                "name": "Mark vehicle available on return",
                "model": "x_rent_contract",
                "trigger": "on_write",
                "description": "When contract status is returned, set vehicle available.",
                "filter_domain": "[('x_status', '=', 'returned')]",
                "safe_actions": [
                    {
                        "kind": "related_write",
                        "relation_field": "x_vehicle_id",
                        "field": "x_status",
                        "value": "available",
                    }
                ],
            },
            {
                "name": "Flag overdue returns",
                "model": "x_rent_contract",
                "trigger": "on_time",
                "description": "Daily: contracts past return due still active → overdue + activity.",
                "safe_actions": [
                    {
                        "kind": "object_write",
                        "field": "x_status",
                        "value": "overdue",
                    },
                    {"kind": "next_activity", "summary": "Overdue vehicle return"},
                ],
            },
        ],
        "reuse_hints": [
            {
                "model": "res.partner",
                "reason": "Link rental customers to Contacts (already in Odoo)",
            },
            {
                "model": "account.move",
                "reason": "Optional later: invoice from payments (accounting stub)",
                "optional": True,
            },
        ],
        "tags": [
            "car",
            "rental",
            "fleet",
            "vehicle",
            "hire",
            "lease",
            "odometer",
            "deposit",
        ],
    }


def clinic_pack() -> dict[str, Any]:
    """Clinic / appointment booking scaffold."""
    appt_status = _sel(
        ("draft", "Draft"),
        ("confirmed", "Confirmed"),
        ("checked_in", "Checked in"),
        ("done", "Done"),
        ("no_show", "No-show"),
        ("cancelled", "Cancelled"),
    )
    return {
        "technical_name": "clinic_booking",
        "display_name": "Clinic Booking",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "clinic",
        "tags": [
            "clinic",
            "appointment",
            "patient",
            "doctor",
            "medical",
            "booking",
            "healthcare",
            "schedule",
        ],
        "models": [
            {
                "model": "x_clinic_practitioner",
                "description": "Practitioner",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                    },
                    {"name": "x_specialty", "ttype": "char", "string": "Specialty"},
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": "x_clinic_patient",
                "description": "Patient",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {"name": "x_dob", "ttype": "date", "string": "Date of Birth"},
                    {"name": "x_notes", "ttype": "text", "string": "Clinical Notes"},
                ],
            },
            {
                "model": "x_clinic_appointment",
                "description": "Appointment",
                "mode": "new",
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Subject", "required": True},
                    {
                        "name": "x_patient_id",
                        "ttype": "many2one",
                        "string": "Patient",
                        "relation": "x_clinic_patient",
                        "required": True,
                    },
                    {
                        "name": "x_practitioner_id",
                        "ttype": "many2one",
                        "string": "Practitioner",
                        "relation": "x_clinic_practitioner",
                        "required": True,
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": appt_status,
                        "required": True,
                    },
                    {"name": "x_start", "ttype": "datetime", "string": "Start", "required": True},
                    {"name": "x_end", "ttype": "datetime", "string": "End"},
                    {"name": "x_reason", "ttype": "char", "string": "Reason"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_clinic_patient",
                "label": "Appointments",
                "related_model": "x_clinic_appointment",
                "relation_field": "x_patient_id",
                "icon": "fa-calendar",
            }
        ],
        "automations": [
            {
                "name": "Remind upcoming appointments",
                "model": "x_clinic_appointment",
                "trigger": "on_time",
                "description": "Activity reminder before start",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Upcoming appointment"}
                ],
            }
        ],
        "reuse_hints": [
            {"model": "res.partner", "reason": "Patients and practitioners as Contacts"}
        ],
    }


def field_service_pack() -> dict[str, Any]:
    """Field service / job dispatch scaffold."""
    job_status = _sel(
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    )
    return {
        "technical_name": "field_service",
        "display_name": "Field Service",
        "depends": ["base", "contacts", "mail"],
        "domain_pack": "field_service",
        "tags": [
            "field",
            "service",
            "dispatch",
            "job",
            "technician",
            "workorder",
            "maintenance",
            "repair",
        ],
        "models": [
            {
                "model": "x_fs_technician",
                "description": "Technician",
                "mode": "new",
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Name", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Contact",
                        "relation": "res.partner",
                    },
                    {"name": "x_skills", "ttype": "char", "string": "Skills"},
                    {"name": "x_active", "ttype": "boolean", "string": "Active"},
                ],
            },
            {
                "model": "x_fs_job",
                "description": "Work Order",
                "mode": "new",
                "mixins": ["mail.thread", "mail.activity.mixin"],
                "fields": [
                    {"name": "x_name", "ttype": "char", "string": "Title", "required": True},
                    {
                        "name": "x_partner_id",
                        "ttype": "many2one",
                        "string": "Customer",
                        "relation": "res.partner",
                        "required": True,
                    },
                    {
                        "name": "x_technician_id",
                        "ttype": "many2one",
                        "string": "Technician",
                        "relation": "x_fs_technician",
                    },
                    {
                        "name": "x_status",
                        "ttype": "selection",
                        "string": "Status",
                        "selection": job_status,
                        "required": True,
                    },
                    {"name": "x_scheduled_start", "ttype": "datetime", "string": "Scheduled"},
                    {"name": "x_address", "ttype": "char", "string": "Site Address"},
                    {"name": "x_notes", "ttype": "text", "string": "Notes"},
                ],
            },
        ],
        "smart_buttons": [
            {
                "on_model": "x_fs_technician",
                "label": "Jobs",
                "related_model": "x_fs_job",
                "relation_field": "x_technician_id",
                "icon": "fa-wrench",
            }
        ],
        "automations": [
            {
                "name": "Activity when job scheduled",
                "model": "x_fs_job",
                "trigger": "on_write",
                "filter_domain": "[('x_status', '=', 'scheduled')]",
                "safe_actions": [
                    {"kind": "next_activity", "summary": "Dispatch job"}
                ],
            }
        ],
        "reuse_hints": [{"model": "res.partner", "reason": "Customers as Contacts"}],
    }


def _hospital_pack() -> dict[str, Any]:
    from app.ai_domain_pack_hospital import hospital_pack

    return hospital_pack()


def _law_firm_pack() -> dict[str, Any]:
    from app.ai_domain_pack_law_firm import law_firm_pack

    return law_firm_pack()


def _restaurant_pack() -> dict[str, Any]:
    from app.ai_domain_pack_restaurant import restaurant_pack

    return restaurant_pack()


def _real_estate_pack() -> dict[str, Any]:
    from app.ai_domain_pack_real_estate import real_estate_pack

    return real_estate_pack()


def _hotel_pack() -> dict[str, Any]:
    from app.ai_domain_pack_hotel import hotel_pack

    return hotel_pack()


def _subscription_pack() -> dict[str, Any]:
    from app.ai_domain_pack_subscription import subscription_pack

    return subscription_pack()


def _project_tracker_pack() -> dict[str, Any]:
    from app.ai_domain_pack_project_tracker import project_tracker_pack

    return project_tracker_pack()


def _retail_supermarket_pack() -> dict[str, Any]:
    from app.ai_domain_pack_retail_supermarket import retail_supermarket_pack

    return retail_supermarket_pack()


_PACK_FACTORIES: list[tuple[str, Any, re.Pattern[str]]] = [
    (
        "car_rental",
        car_rental_pack,
        re.compile(
            r"\b(car[\s-]?rental|vehicle[\s-]?rental|fleet[\s-]?rental|"
            r"rent[\s-]?a[\s-]?car|auto[\s-]?hire|car[\s-]?hire)\b",
            re.I,
        ),
    ),
    # Hospital BEFORE clinic — "hospital" must not fall through to thin clinic booking.
    (
        "hospital",
        _hospital_pack,
        re.compile(
            r"\b(hospital|inpatient|world[\s-]?class\s+hospital|ward|icu|emergency\s+room|"
            r"\ber\b|operating\s+theatre|pharmacy|radiology|triage|admission|"
            r"hospital\s+management)\b",
            re.I,
        ),
    ),
    (
        "law_firm",
        _law_firm_pack,
        re.compile(
            r"\b(law\s*firm|legal\s+practice|practice\s+management|attorney|"
            r"lawyer|litigation|counsel|matter\s+management|legal\s+ops|"
            r"world[\s-]?class\s+law|billable\s+hour|retainer|trust\s+account)\b",
            re.I,
        ),
    ),
    # Hotel before real_estate — "property" alone is ambiguous; hotel prompts use PMS/check-in.
    (
        "hotel",
        _hotel_pack,
        re.compile(
            r"\b(hotel|pms|property\s+management\s+system|check[\s-]?in|check[\s-]?out|"
            r"housekeeping|front\s+desk|room\s+booking|hotel\s+management|lodging|guest\s+folio)\b",
            re.I,
        ),
    ),
    (
        "restaurant",
        _restaurant_pack,
        re.compile(
            r"\b(restaurant|dining|menu|kitchen|food\s+service|pos\s+lite|"
            r"table\s+reservation|waiter|bistro|cafe|dining\s+order)\b",
            re.I,
        ),
    ),
    (
        "retail_supermarket",
        _retail_supermarket_pack,
        re.compile(
            r"\b(super[\s-]?market|grocery|mega\s+store|retail\s+chain|"
            r"multiple\s+branches|store\s+chain|hypermarket)\b",
            re.I,
        ),
    ),
    (
        "real_estate",
        _real_estate_pack,
        re.compile(
            r"\b(real\s*estate|rental\s+property|lease\s+management|tenant\s+portal|"
            r"property\s+listing|unit\s+lease|viewing|landlord|apartment\s+rental)\b",
            re.I,
        ),
    ),
    (
        "subscription",
        _subscription_pack,
        re.compile(
            r"\b(subscription|membership\s+plan|renewal\s+workflow|saas\s+plan|"
            r"usage[\s-]?based|member\s+portal)\b",
            re.I,
        ),
    ),
    (
        "project_tracker",
        _project_tracker_pack,
        re.compile(
            r"\b(project\s+tracker|project\s+management|task\s+tracker|milestone|"
            r"time\s+entry|timesheet|pm\s+tool)\b",
            re.I,
        ),
    ),
    (
        "clinic",
        clinic_pack,
        re.compile(
            # Avoid bare patient|doctor — those appear inside hospital prompts too.
            r"\b(clinic|outpatient\s+clinic|medical\s+practice|"
            r"healthcare\s+booking|appointment\s+booking)\b",
            re.I,
        ),
    ),
    (
        "field_service",
        field_service_pack,
        re.compile(
            r"\b(field\s+service|job\s+dispatch|work\s*order|technician\s+dispatch)\b",
            re.I,
        ),
    ),
]


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def score_domain_pack(prompt: str, pack: dict[str, Any]) -> float:
    """Cheap local retrieval: Jaccard over prompt tokens vs pack tags + model labels."""
    pt = _tokenize(prompt)
    if not pt:
        return 0.0
    bag: set[str] = set()
    for tag in pack.get("tags") or []:
        bag |= _tokenize(str(tag))
    bag |= _tokenize(str(pack.get("display_name") or ""))
    bag |= _tokenize(str(pack.get("domain_pack") or ""))
    for m in pack.get("models") or []:
        if isinstance(m, dict):
            bag |= _tokenize(str(m.get("description") or ""))
            bag |= _tokenize(str(m.get("model") or "").replace("_", " ").replace("x ", ""))
    if not bag:
        return 0.0
    inter = len(pt & bag)
    union = len(pt | bag)
    return inter / union if union else 0.0


def _all_packs() -> list[tuple[str, dict[str, Any]]]:
    return [(pack_id, factory()) for pack_id, factory, _ in _PACK_FACTORIES]


def retrieve_domain_pack_lexical(
    prompt: str, *, min_score: float = 0.08
) -> tuple[str, dict[str, Any], float] | None:
    """Regex first, then Jaccard — no embeddings."""
    text = (prompt or "").strip()
    if not text:
        return None
    for pack_id, factory, pattern in _PACK_FACTORIES:
        if pattern.search(text):
            pack = copy.deepcopy(factory())
            return pack_id, pack, 1.0
    best: tuple[str, dict[str, Any], float] | None = None
    for pack_id, factory, _pattern in _PACK_FACTORIES:
        pack = factory()
        score = score_domain_pack(text, pack)
        if score >= min_score and (best is None or score > best[2]):
            best = (pack_id, copy.deepcopy(pack), score)
    return best


def retrieve_domain_pack(
    prompt: str, *, min_score: float = 0.08, provider: Any | None = None
) -> tuple[str, dict[str, Any], float] | None:
    """Step 0 retrieval: embedding RAG when available, else regex/Jaccard.

    Returns (pack_id, pack, score). Score is cosine (embeddings) or Jaccard/1.0 (regex).
    When ``AI_SELF_CONSISTENCY=on`` and a provider is supplied, runs pack-id vote/merge.
    """
    from app.ai_rag import retrieve_with_rag

    pack_id, pack, score, method = retrieve_with_rag(
        prompt,
        pack_loader=_all_packs,
        jaccard_retrieve=lambda p: retrieve_domain_pack_lexical(p, min_score=min_score),
    )
    baseline: tuple[str, dict[str, Any], float] | None = None
    if method != "none" and pack_id:
        if isinstance(pack, dict):
            pack = copy.deepcopy(pack)
            pack["_retrieval"] = {"method": method, "score": score}
        baseline = pack_id, pack, score

    from app.ai_self_consistency import (
        retrieve_scaffold_with_consistency,
        self_consistency_enabled,
    )

    if self_consistency_enabled() and provider is not None:
        voted, warnings = retrieve_scaffold_with_consistency(
            prompt,
            provider,
            baseline=baseline,
            pack_loader=_all_packs,
        )
        if voted is not None:
            pid, p, sc = voted
            if warnings and isinstance(p, dict):
                p.setdefault("_self_consistency_warnings", warnings)
            return pid, p, sc
        return baseline

    return baseline


def match_domain_pack(prompt: str) -> tuple[str, dict[str, Any]] | None:
    """Strict regex-only match for offline / AI-off paths (no Jaccard false positives)."""
    text = (prompt or "").strip()
    if not text:
        return None
    for pack_id, factory, pattern in _PACK_FACTORIES:
        if pattern.search(text):
            return pack_id, copy.deepcopy(factory())
    return None


def merge_domain_pack(
    draft: dict[str, Any], pack: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Fill missing models/fields/smart_buttons/automations from pack; keep AI extras."""
    warnings: list[str] = []
    out = copy.deepcopy(draft)
    out.setdefault("technical_name", pack.get("technical_name"))
    out.setdefault("display_name", pack.get("display_name"))
    out["domain_pack"] = pack.get("domain_pack")
    if pack.get("reuse_stock"):
        out["_pack_reuse_stock"] = copy.deepcopy(pack.get("reuse_stock"))

    depends = list(out.get("depends") or [])
    for dep in pack.get("depends") or []:
        if dep not in depends:
            depends.append(dep)
    out["depends"] = depends or ["base"]

    draft_models = {
        m.get("model"): m
        for m in (out.get("models") or [])
        if isinstance(m, dict) and m.get("model")
    }
    merged_models: list[dict[str, Any]] = []
    seen: set[str] = set()

    for pm in pack.get("models") or []:
        if not isinstance(pm, dict) or not pm.get("model"):
            continue
        mid = pm["model"]
        seen.add(mid)
        if mid not in draft_models:
            merged_models.append(copy.deepcopy(pm))
            warnings.append(f"domain pack added model {mid}")
            leaf = mid.replace("x_", "")
            if any(
                k in leaf
                for k in (
                    "attorney",
                    "doctor",
                    "staff",
                    "bill",
                    "invoice",
                    "compliance",
                    "deposit",
                    "trust",
                )
            ):
                warnings.append(
                    f"generation gap: pack supplied core model {mid} "
                    "(LLM under-covered scaffold — raise prompt adherence)"
                )
            continue
        dm = copy.deepcopy(draft_models[mid])
        existing_by_name = {
            f.get("name"): f
            for f in (dm.get("fields") or [])
            if isinstance(f, dict) and f.get("name")
        }
        fields = list(dm.get("fields") or [])
        for pf in pm.get("fields") or []:
            if not isinstance(pf, dict) or not pf.get("name"):
                continue
            fname = pf["name"]
            if fname not in existing_by_name:
                fields.append(copy.deepcopy(pf))
                warnings.append(f"domain pack added field {mid}.{fname}")
                continue
            # Upgrade thin/truncated selections from pack (LLM kept weaker keys)
            df = existing_by_name[fname]
            if (
                str(pf.get("ttype") or df.get("ttype")) == "selection"
                and pf.get("selection")
                and df.get("selection")
            ):
                pack_keys = set(
                    re.findall(r"\(\s*'([^']+)'\s*,", str(pf.get("selection") or ""))
                )
                draft_keys = set(
                    re.findall(r"\(\s*'([^']+)'\s*,", str(df.get("selection") or ""))
                )
                if len(pack_keys) > len(draft_keys):
                    df["selection"] = pf["selection"]
                    if pf.get("string") and not df.get("string"):
                        df["string"] = pf["string"]
                    warnings.append(
                        f"domain pack upgraded selection {mid}.{fname} "
                        f"({len(draft_keys)}→{len(pack_keys)} keys)"
                    )
            # Fix wrong M2O targets (e.g. fee earner → res.users instead of x_attorney)
            if (
                str(pf.get("ttype") or df.get("ttype")) == "many2one"
                and pf.get("relation")
                and str(df.get("relation") or "") != str(pf.get("relation"))
            ):
                pref = str(pf["relation"])
                cur = str(df.get("relation") or "")
                prefer_pack = False
                fname = str(df.get("name") or pf.get("name") or "").lower()
                # Keep generic assignee/login on res.users even if pack points at staff
                if fname in {"x_assignee_id", "assignee_id", "x_user_id", "user_id"}:
                    prefer_pack = False
                elif pref.startswith("x_") and cur in {
                    "res.users",
                    "hr.employee",
                    "",
                    "False",
                }:
                    prefer_pack = True
                elif pref.startswith("x_") and cur.startswith("res."):
                    prefer_pack = True
                if prefer_pack:
                    df["relation"] = pref
                    if pf.get("string"):
                        df["string"] = pf["string"]
                    warnings.append(
                        f"domain pack fixed relation {mid}.{fname} "
                        f"{cur or '(empty)'} → {pref}"
                    )
            if pf.get("required") and not df.get("required"):
                df["required"] = True
                warnings.append(f"domain pack set required {mid}.{fname}")
        dm["fields"] = fields
        if not dm.get("description") and pm.get("description"):
            dm["description"] = pm["description"]
        if pm.get("is_workflow") and not dm.get("is_workflow"):
            # Don't promote party-link stubs here — quality demotes those
            leaf = mid.replace("x_", "")
            if not any(k in leaf for k in ("party", "role_link", "participant")):
                dm["is_workflow"] = True
        merged_models.append(dm)

    for mid, dm in draft_models.items():
        if mid not in seen:
            merged_models.append(copy.deepcopy(dm))

    out["models"] = merged_models

    if not out.get("smart_buttons") and pack.get("smart_buttons"):
        out["smart_buttons"] = copy.deepcopy(pack["smart_buttons"])
        warnings.append("domain pack added smart_buttons")
    elif pack.get("smart_buttons"):
        existing = {
            (b.get("on_model"), b.get("related_model"), b.get("relation_field"))
            for b in (out.get("smart_buttons") or [])
            if isinstance(b, dict)
        }
        for btn in pack["smart_buttons"]:
            key = (btn.get("on_model"), btn.get("related_model"), btn.get("relation_field"))
            if key not in existing:
                out.setdefault("smart_buttons", []).append(copy.deepcopy(btn))

    if not out.get("automations") and pack.get("automations"):
        out["automations"] = copy.deepcopy(pack["automations"])
        warnings.append("domain pack added automations metadata")
    elif pack.get("automations"):
        names = {
            a.get("name")
            for a in (out.get("automations") or [])
            if isinstance(a, dict)
        }
        for auto in pack["automations"]:
            if auto.get("name") not in names:
                out.setdefault("automations", []).append(copy.deepcopy(auto))

    if pack.get("reuse_hints"):
        out["reuse_hints"] = copy.deepcopy(pack["reuse_hints"])
    if pack.get("tags"):
        out.setdefault("tags", pack["tags"])

    return out, warnings


def list_domain_packs() -> list[dict[str, str]]:
    out = []
    for pack_id, factory, _ in _PACK_FACTORIES:
        pack = factory()
        out.append(
            {
                "id": pack_id,
                "display_name": str(pack.get("display_name") or pack_id),
                "tags": ",".join(pack.get("tags") or []),
            }
        )
    return out


__all__ = [
    "car_rental_pack",
    "clinic_pack",
    "field_service_pack",
    "hospital_pack",
    "hotel_pack",
    "law_firm_pack",
    "project_tracker_pack",
    "real_estate_pack",
    "restaurant_pack",
    "subscription_pack",
    "match_domain_pack",
    "merge_domain_pack",
    "retrieve_domain_pack",
    "retrieve_domain_pack_lexical",
    "score_domain_pack",
    "list_domain_packs",
]


def hospital_pack() -> dict[str, Any]:
    """Re-export for tests and callers."""
    return _hospital_pack()


def law_firm_pack() -> dict[str, Any]:
    """Re-export for tests and callers."""
    return _law_firm_pack()


def restaurant_pack() -> dict[str, Any]:
    return _restaurant_pack()


def real_estate_pack() -> dict[str, Any]:
    return _real_estate_pack()


def hotel_pack() -> dict[str, Any]:
    return _hotel_pack()


def subscription_pack() -> dict[str, Any]:
    return _subscription_pack()


def project_tracker_pack() -> dict[str, Any]:
    return _project_tracker_pack()

