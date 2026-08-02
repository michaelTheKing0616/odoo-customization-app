"""Industry seed CSV packs for Bulk Import — tied to domain packs + common models."""

from __future__ import annotations

from typing import Any


def _pack(
    pack_id: str,
    *,
    name: str,
    description: str,
    models: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": pack_id,
        "name": name,
        "description": description,
        "models": [
            {"model": model, "filename": f"{pack_id}_{model.replace('.', '_')}.csv", "csv": csv}
            for model, csv in models.items()
        ],
    }


def partner_seed() -> dict[str, Any]:
    return _pack(
        "partners",
        name="Contacts & companies",
        description="Sample customers and companies for res.partner",
        models={
            "res.partner": (
                "name,email,phone,is_company,street,city,vat\n"
                "Acme Logistics,ops@acme.example,+2348010000001,true,12 Marina,Lagos,NG123456789\n"
                "Jane Adeyemi,jane.adeyemi@example.com,+2348010000002,false,4 Admiralty Way,Lagos,\n"
                "Northwind Traders,buy@northwind.example,+15551234001,true,1 Harbor Rd,Abuja,NG987654321\n"
                "Chidi Okonkwo,chidi@example.com,+2348010000003,false,9 Ring Road,Ibadan,\n"
            ),
        },
    )


def product_seed() -> dict[str, Any]:
    return _pack(
        "products",
        name="Products",
        description="Sample product.template rows (consumable + service)",
        models={
            "product.template": (
                "name,default_code,list_price,type,sale_ok\n"
                "Day Rental Fee,RENT-DAY,45.00,service,true\n"
                "Insurance Add-on,INS-ADD,12.50,service,true\n"
                "GPS Tracker Kit,GPS-KIT,89.00,consu,true\n"
                "Child Seat,CHILD-SEAT,8.00,consu,true\n"
            ),
        },
    )


def car_rental_seed() -> dict[str, Any]:
    return _pack(
        "car_rental",
        name="Car rental fleet",
        description="Branches, vehicles, and draft contracts for x_rent_* models",
        models={
            "x_rent_branch": (
                "x_name,x_code,x_address,x_phone\n"
                "Lagos Island,LOS,12 Marina Lagos,+2348011110001\n"
                "Abuja Central,ABJ,1 Shehu Shagari Way,+2348011110002\n"
            ),
            "x_rent_vehicle": (
                "x_name,x_plate,x_status,x_daily_rate,x_category\n"
                "Toyota Corolla 2022,ABC-101-LA,available,45.00,economy\n"
                "Honda CR-V 2023,XYZ-202-LA,available,75.00,suv\n"
                "Mercedes E-Class,LUX-303-AB,maintenance,150.00,luxury\n"
                "Toyota Hiace,VAN-404-LA,available,95.00,van\n"
            ),
            "x_rent_contract": (
                "x_name,x_start_date,x_end_date,x_status\n"
                "CNT-2026-0001,2026-08-01,2026-08-05,draft\n"
                "CNT-2026-0002,2026-08-10,2026-08-17,draft\n"
            ),
        },
    )


def library_seed() -> dict[str, Any]:
    return _pack(
        "library",
        name="Library books",
        description="Sample books for Acme Library (x_lib_book)",
        models={
            "x_lib_book": (
                "x_name,x_isbn,x_copies,x_status,x_fine_rate\n"
                "Things Fall Apart,9780385474542,3,available,100.0\n"
                "Half of a Yellow Sun,9780007200283,2,available,100.0\n"
                "Americanah,9780307455925,4,available,80.0\n"
                "The Beautiful Ones Are Not Yet Born,9780435905408,1,available,50.0\n"
            ),
        },
    )


def clinic_seed() -> dict[str, Any]:
    return _pack(
        "clinic",
        name="Clinic patients",
        description="Sample patients for clinic domain pack models",
        models={
            "x_clinic_patient": (
                "x_name,x_phone,x_dob,x_notes\n"
                "Amina Bello,+2348020001001,1990-04-12,New patient\n"
                "Tunde Bakare,+2348020001002,1985-11-03,Follow-up hypertension\n"
                "Ngozi Eze,+2348020001003,2001-07-21,\n"
            ),
            "x_clinic_appointment": (
                "x_name,x_date,x_status\n"
                "APT-001,2026-08-02 09:00:00,scheduled\n"
                "APT-002,2026-08-02 10:30:00,scheduled\n"
            ),
        },
    )


def field_service_seed() -> dict[str, Any]:
    return _pack(
        "field_service",
        name="Field service tickets",
        description="Work orders / tickets for field service pack models",
        models={
            "x_fs_ticket": (
                "x_name,x_priority,x_status,x_scheduled_date\n"
                "Install router — Ikeja,high,open,2026-08-03\n"
                "Replace POS printer — VI,normal,open,2026-08-04\n"
                "Annual HVAC check — Abuja,low,planned,2026-08-10\n"
            ),
        },
    )


_SEED_FACTORIES = [
    partner_seed,
    product_seed,
    car_rental_seed,
    library_seed,
    clinic_seed,
    field_service_seed,
]


def list_seed_packs() -> list[dict[str, Any]]:
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "models": [m["model"] for m in p["models"]],
        }
        for p in (_f() for _f in _SEED_FACTORIES)
    ]


def get_seed_pack(pack_id: str) -> dict[str, Any] | None:
    for factory in _SEED_FACTORIES:
        pack = factory()
        if pack["id"] == pack_id:
            return pack
    return None


def template_csv_for_model(model: str) -> str | None:
    """Return first matching seed CSV for a model technical name."""
    for factory in _SEED_FACTORIES:
        pack = factory()
        for entry in pack["models"]:
            if entry["model"] == model:
                return entry["csv"]
    # Aliases used in older templates
    aliases = {
        "x_rental_vehicle": "x_rent_vehicle",
        "x_vehicle": "x_rent_vehicle",
        "x_rental_contract": "x_rent_contract",
        "x_contract": "x_rent_contract",
        "x_book": "x_lib_book",
    }
    aliased = aliases.get(model)
    if aliased:
        return template_csv_for_model(aliased)
    return None
