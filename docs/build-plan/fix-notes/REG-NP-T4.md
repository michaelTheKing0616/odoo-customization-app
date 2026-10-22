FIXNOTE REG-NP-T4 · after 2 loops at L3
root cause: apps/api/tests/test_reg_np_t4.py:230-237 `_imports` records `ast.Import` alias.name and `ast.ImportFrom.module` only. It drops ImportFrom alias names,
  and it skips ImportFrom entirely when `node.module` is None (relative `from . import x`). The segment check at :664-666 therefore sees `app` for
  `from app import llm_gateway` and nothing for `from .. import llm_gateway`. The AC6 pin passes on those imports when it should fail.
change: edit only apps/api/tests/test_reg_np_t4.py, inside `_imports` (:230-237).
  1. Keep the `ast.Import` branch as is.
  2. For every `ast.ImportFrom`, drop the `and node.module` guard. Set base = node.module or "". For each alias in node.names, append
     f"{base}.{alias.name}" when base is set, else alias.name. Also append base when it is set, so `from app.llm_gateway import x` still fails.
  3. Do not change :128-130 `_FORBIDDEN_IMPORT_ROOTS`, the dotted `module.split(".")` intersection at :664-666, `_call_names`, `_APPLY_NAMES`,
     or the apply-call assertion at :667-670.
do not: edit app/wireframe, rename or narrow `_FORBIDDEN_IMPORT_ROOTS`, swap the segment check for a prefix or startswith match,
  drop or loosen the apply-call loop, add a skip or xfail, or treat a green run with no proof of rejection as done (that was loop 2).
verify: cd apps/api && uv run pytest -q tests/test_reg_np_t4.py → 18 passed (also run it in reverse order, as T0 did).
  proof (one line, no file edits): cd apps/api && uv run python -c "import ast,sys; sys.path.insert(0,'tests'); import test_reg_np_t4 as t; m=t._imports(ast.parse('from app import llm_gateway\nfrom .. import changeset')); assert all(t._FORBIDDEN_IMPORT_ROOTS & set(x.split('.')) for x in m), m; print('rejected', m)"
  → prints `rejected ['app', 'app.llm_gateway', 'changeset']`.
