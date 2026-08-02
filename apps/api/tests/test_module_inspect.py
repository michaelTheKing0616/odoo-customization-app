"""Tests for zip model-name extraction."""

from __future__ import annotations

from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip

from app.module_inspect import extract_model_names_from_zip


def test_extract_python_mode_models() -> None:
    raw = build_module_zip(
        ModuleSpec(
            technical_name="demo_models",
            display_name="Demo Models",
            models=[
                ModelSpec(
                    model="x_ticket",
                    description="Ticket",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    assert extract_model_names_from_zip(raw) == ["x_ticket"]


def test_extract_data_mode_models() -> None:
    raw = build_module_zip(
        ModuleSpec(
            technical_name="demo_data",
            display_name="Demo Data",
            install_mode="data",
            models=[
                ModelSpec(
                    model="x_data",
                    description="Data",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    assert "x_data" in extract_model_names_from_zip(raw)
