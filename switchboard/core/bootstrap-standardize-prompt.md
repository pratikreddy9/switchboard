# Bootstrap Standardize Prompt

Use everything you can safely inspect in the available project directories to standardize this project into the Switchboard format.

Requirements:
- Read `switchboard/core/playbook.md` first.
- Inspect the project root and known subpaths.
- Find existing readmes, changelogs, runbooks, handoff notes, agent instructions, and operational docs.
- Preserve useful information, but rewrite it into the Switchboard standard files under `switchboard/`.
- Do not overwrite unrelated project docs outside `switchboard/` unless explicitly asked.
- Put the actual structured update in `switchboard/local/tasks-completed.md`, not directly into derived docs.
- If the project has known ports, health checks, or run command hints, include them in the latest `tasks-completed.md` entry under a `Runtime:` block.
- If project root docs should be framework-owned, record the needed `Readme`, `API`, `Changelog`, and `Version` blocks in `tasks-completed.md` and enable those docs through the node managed-doc config.
- Record the standardization work in `switchboard/local/tasks-completed.md` using the required entry format.
- Finish by running `switchboard node snapshot --project-root <path>`.
