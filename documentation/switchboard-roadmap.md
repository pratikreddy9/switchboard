# Switchboard Roadmap

## North Star

One- or two-click GitHub backup for every tracked project, with safe credentials and visible per-project status.

## Current Priority

Agent behavior comes first. Agents must learn Switchboard rules from one generated contract and one tool-native entrypoint per CLI, then pass the update gate before their work counts as complete.

## Phases

1. Agent Contract Gate
   - Generate contract files for Codex, Claude Code, Gemini CLI, Qwen Code, opencode, and generic agents.
   - Require read-back, scope check, snapshot, and `verify-update`.

2. One Node Per Machine
   - Move toward one Switchboard node per machine and one control port.
   - Keep manager-node and minion-node roles explicit.

3. Safe Node Actions And Pull Authority
   - Make manager-vs-node authority visible.
   - Allow safe scoped actions only; cleanup must move or zip, never delete.

4. Project Intelligence UI
   - Fix project grouping selection.
   - Add project colors and one dependency/composition/model-usage view.

5. GitHub Backup
   - Add credential handling.
   - Batch backup eligible repos with pre-push safety checks.

## Operating Principles

- Read back before acting.
- Ask in simple English when intent is unclear.
- Make small, surgical changes.
- Do not add ceremony.
- Verify with observable checks.
