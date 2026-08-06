"""Expert interview → IngestBatch (ING-9)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.ingest.constants import NATURAL_KEY_FIELDS
from app.ingest.schema import DocType, IngestBatch, IngestFile, IngestRow, IngestTable


class InterviewQuestion(BaseModel):
    id: str
    prompt: str
    kind: Literal["text", "choice", "lines"] = "text"
    choices: list[str] = Field(default_factory=list)


class InterviewAnswers(BaseModel):
    business_name: str = ""
    product_lines: list[str] = Field(default_factory=list)
    product_type: Literal["product", "service", "mixed"] = "mixed"
    starter_contacts: list[str] = Field(default_factory=list)
    expense_categories: list[str] = Field(default_factory=list)


INTERVIEW_QUESTIONS: list[InterviewQuestion] = [
    InterviewQuestion(
        id="business_name",
        prompt="What is your business name?",
        kind="text",
    ),
    InterviewQuestion(
        id="product_type",
        prompt="Do you sell physical products, services, or both?",
        kind="choice",
        choices=["product", "service", "mixed"],
    ),
    InterviewQuestion(
        id="product_lines",
        prompt="List starter products or services (one per line: Name | SKU | Price)",
        kind="lines",
    ),
    InterviewQuestion(
        id="starter_contacts",
        prompt="List starter customers (one per line: Name | Email | Phone)",
        kind="lines",
    ),
    InterviewQuestion(
        id="expense_categories",
        prompt="Optional: expense categories for later CoA alignment (one per line)",
        kind="lines",
    ),
]


def _parse_pipe_lines(lines: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        out.append(parts)
    return out


def build_batch_from_interview(
    *,
    connection_id: str,
    answers: InterviewAnswers,
) -> IngestBatch:
    file_id = str(uuid.uuid4())
    batch = IngestBatch(
        connection_id=connection_id,
        source="interview",
        files=[
            IngestFile(
                id=file_id,
                filename="expert-interview.json",
                mime="application/json",
                doc_type="other",
                confidence=1.0,
                needs_user_confirm=False,
            )
        ],
    )
    tables: list[IngestTable] = []

    contact_rows: list[IngestRow] = []
    for idx, parts in enumerate(_parse_pipe_lines(answers.starter_contacts), start=1):
        name = parts[0] if parts else ""
        email = parts[1] if len(parts) > 1 else ""
        phone = parts[2] if len(parts) > 2 else ""
        if not name and not email:
            continue
        contact_rows.append(
            IngestRow(
                raw={"name": name, "email": email, "phone": phone},
                values={},
                source_ref=f"interview:contact:{idx}",
            )
        )
    if contact_rows:
        tid = str(uuid.uuid4())
        tables.append(
            IngestTable(
                id=tid,
                model="res.partner",
                doc_type="customer_list",
                mapping={"name": "name", "email": "email", "phone": "phone"},
                natural_key_fields=NATURAL_KEY_FIELDS["res.partner"],
                rows=contact_rows,
            )
        )
        batch.files[0].table_ids.append(tid)

    product_rows: list[IngestRow] = []
    default_type = "service" if answers.product_type == "service" else "consu"
    for idx, parts in enumerate(_parse_pipe_lines(answers.product_lines), start=1):
        name = parts[0] if parts else ""
        code = parts[1] if len(parts) > 1 else f"SKU-{idx:03d}"
        price = parts[2] if len(parts) > 2 else "0"
        ptype = "service" if answers.product_type == "service" else default_type
        if answers.product_type == "mixed" and len(parts) > 3:
            ptype = parts[3].strip() or ptype
        if not name:
            continue
        product_rows.append(
            IngestRow(
                raw={
                    "name": name,
                    "default_code": code,
                    "list_price": price,
                    "type": ptype,
                },
                values={},
                source_ref=f"interview:product:{idx}",
            )
        )
    if product_rows:
        tid = str(uuid.uuid4())
        tables.append(
            IngestTable(
                id=tid,
                model="product.template",
                doc_type="product_catalog",
                mapping={
                    "name": "name",
                    "default_code": "default_code",
                    "list_price": "list_price",
                    "type": "type",
                },
                natural_key_fields=NATURAL_KEY_FIELDS["product.template"],
                rows=product_rows,
            )
        )
        batch.files[0].table_ids.append(tid)

    if answers.expense_categories:
        # Guidance only — product.category rows for ops structure, never invent posted CoA
        cat_rows: list[IngestRow] = []
        for idx, line in enumerate(answers.expense_categories, start=1):
            name = line.strip()
            if not name:
                continue
            cat_rows.append(
                IngestRow(
                    raw={"name": name},
                    values={},
                    source_ref=f"interview:expense_cat:{idx}",
                    flags=["interview_guidance_only"],
                )
            )
        if cat_rows:
            tid = str(uuid.uuid4())
            tables.append(
                IngestTable(
                    id=tid,
                    model="product.category",
                    doc_type="other",
                    mapping={"name": "name"},
                    natural_key_fields=["name"],
                    rows=cat_rows,
                    warnings=[
                        "Expense categories mapped to product.category for structure only — "
                        "do not treat as fiscal CoA; align accounts via l10n_* separately"
                    ],
                )
            )
            batch.files[0].table_ids.append(tid)
        batch.warnings.append(
            "expense categories → product.category guidance (not posted CoA): "
            + ", ".join(answers.expense_categories[:8])
        )
    if answers.business_name:
        batch.warnings.append(f"business: {answers.business_name}")

    batch.tables = tables
    return batch
