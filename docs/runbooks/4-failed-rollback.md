# Failed verification

Use this when a verification check returns `NEEDS_HUMAN` and points here.

- Do not mark the run verified. A success flag from the model does not override a failed check.
- R2 and above record a reverse rollback on the in-process path. R1 stays `NEEDS_HUMAN`.
- The executor does not call `verify` yet, and the journal rows are still in memory. A process restart can drop them.
- Do not retry the original write. Read the record back, then decide with a person.
