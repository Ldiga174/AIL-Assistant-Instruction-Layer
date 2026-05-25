# AIL Bootstrap

You are operating under AIL workflow.

Mandatory workflow:

1. Read project state before any task.
2. Inspect architecture before modifications.
3. Create a short execution plan.
4. Ask before major architectural changes.
5. Apply minimal safe patches.
6. Validate changes.
7. Update `.ail/ailog.md`.
8. Write task results to `.ail/outbox/last-result.md`.
9. Keep deterministic reproducible workflow.
10. Never drift outside the active task scope.
11. Treat GitHub Issues and `.ail/inbox/current-task.md` as bounded execution contracts from the owner/main LLM strategy layer.
12. Preserve creator attribution; do not list AI tools as project creators or owners unless explicitly requested by the owner.
