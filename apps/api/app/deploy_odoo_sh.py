"""Odoo.sh deployment guide injected into export zips (TIER-2)."""

from __future__ import annotations

import io
import zipfile


def deploy_odoo_sh_markdown(
    *,
    technical_name: str,
    display_name: str,
    odoo_major: int,
    staging_branch: str = "staging",
    production_branch: str = "production",
) -> str:
    return f"""# Deploy {display_name} to Odoo.sh

Module technical name: `{technical_name}`  
Target Odoo major: **{odoo_major}**

## 1. Add the module to your Odoo.sh repository

1. Unzip this export into your Git repo under the addons path (commonly `addons/{technical_name}/` or a custom addons folder configured on Odoo.sh).
2. Ensure `__manifest__.py` lists correct `depends` for your staging database.
3. Commit on branch `{staging_branch}`.

## 2. Push staging and validate

```bash
git checkout {staging_branch}
git add addons/{technical_name}
git commit -m "Add {technical_name} module"
git push origin {staging_branch}
```

Wait for the Odoo.sh build. Install/upgrade the module on the **staging** database from Apps.

Run the matching-major sandbox gate in this tool against the same zip before merging to production.

## 3. Promote to production

```bash
git checkout {production_branch}
git merge {staging_branch}
git push origin {production_branch}
```

Upgrade the module on the production database after the build completes.

## Notes

- Branch names above are suggestions — match your Odoo.sh project conventions.
- Never skip staging when the module adds models, fields, or access rules.
- Python code requires Odoo.sh filesystem install (not Odoo Online).
"""


def inject_file_into_zip(zip_bytes: bytes, member_path: str, content: str | bytes) -> bytes:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zin:
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == member_path:
                    continue
                zout.writestr(item, zin.read(item.filename))
            zout.writestr(member_path, payload)
    return buf.getvalue()
