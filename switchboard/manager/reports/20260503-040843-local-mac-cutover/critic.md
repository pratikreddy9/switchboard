# Local Mac Cutover Critic Pass

## Verdict
The local Mac cutover matches the approved plan. No blocking gap remains for this phase.

## Requirement Check
1. Future plan/design principles: present in `documentation/switchboard-roadmap.md` and `documentation/switchboard-design-principles.md`.
2. Dependency composition/model usage: present in the dependency summary UI and April 29 audit.
3. Sink pull authority clarity: present in pull bundle authority fields and audit.
4. Project grouping dropdown: already repaired in the April 29 UI pass.
5. One node per machine: now true locally for Switchboard manager runtime, with one listener on `8010`.
6. Install/release/update flow: manager-owned install/register/upgrade/verify entrypoints exist.
7. Safe scoped commands: manager actions are allowlisted; cleanup archives instead of deleting.
8. Agent files: Codex, Claude, Gemini, Qwen, and opencode contract files were generated for adaptivelearning.
9. Task ledger colors/hierarchy: already repaired in the April 29 UI pass.
10. Agent habit discovery: evidence came from `.47`; this cutover used that result and did not invent new findings.
11. Read-back/design principles: echoed in ledger entries, reports, and agent contracts.
12. Global/project principles: stored in manifests and agent contracts.
13. Output/token diet: one canonical ledger entry per root; no extra project handoff docs were added.
14. One node/multiple services technology: manager node plus registered roots is active locally.
15. GitHub one-click backup: still intentionally limited to credential-ready repos; credential UX remains deferred.
16. Build/push irony: local code was tested and installed before runtime cutover; no old node was left as the active Switchboard runtime.

## Residual Risk
- The manager archive is large because it preserves the old dashboard runtime environment. It is ignored by git and kept only for rollback.
- Adaptivelearning now has new untracked Switchboard files alongside pre-existing app edits; its app files were not modified by the cutover.
