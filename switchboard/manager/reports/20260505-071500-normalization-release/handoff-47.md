# .47 Manager Handoff

## Last Known State

- Manager: `127.0.0.1:8720`
- Old node ports `8701-8710`: stopped after switchover rehearsal
- Roots: `10` roots verified through manager
- Deletes: none
- Rollback commands: in the `.47` switchover postflight report

## Required Order

1. Run read-only preflight first.
2. Confirm manager `8720` is active.
3. Confirm old `8701-8710` listeners remain stopped.
4. For each root: run normalize, snapshot, verify, pull bundle, postflight.
5. Pull bundle reports must state source authority: node-local or manager/control-center.
6. Verify excludes for secrets, venvs, caches, logs, runtime files, build output, and removed tech.
7. Archive old scaffolding only after every root verifies `ok` and rollback notes are written.

## Hard Rules

- Do not start old ports `8701-8710`.
- Do not delete files.
- Do not hand-edit derived evidence when `switchboard node snapshot` can generate it.
- Do not call the run complete until every pull bundle has a source authority and safe exclude proof.
