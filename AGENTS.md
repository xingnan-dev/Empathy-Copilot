# Instructions for coding agents

Before changing this project, read in order:

1. `docs/PRD.md`
2. `docs/AGENT_DESIGN.md`
3. The current document under `docs/phases/`
4. `docs/PROJECT_STATE.md`

Rules:

- Do not expand functionality beyond the active phase.
- Do not add frameworks for display or speculation.
- Do not remove or flatten evidence provenance.
- Do not delegate deterministic safety decisions entirely to an LLM.
- Do not change product direction without explicit authorization.
- Keep action intent and lifecycle status as separate concepts.
- Add or update tests whenever domain behavior changes.

## Project Context Synchronization

- Before substantial work, read `docs/PROJECT_STATE.md`.
- Treat the Git repository and committed project documentation as the source of truth.
- Check `git status` before modifying files.
- Work only within the current active phase.
- Do not expand scope without explicit instruction.
- Do not modify `ui-prototype/` unless explicitly instructed.
- If a prompt conflicts with `docs/PROJECT_STATE.md` or the current repository state, report the conflict before making changes.
- After an approved phase is completed, update `docs/PROJECT_STATE.md` to reflect the new frozen state.
