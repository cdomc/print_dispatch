# Project: Print Dispatch (Windows, PDF-only)

Codex MUST follow specs in /spec exactly.

## Non-negotiables
- Do not modify files in /spec unless explicitly instructed.
- No silent heuristics. If uncertain -> BLOCK or require explicit operator confirmation in UI.
- PDF-only input. Windows target environment.
- Any PDF containing any A4 page -> whole file goes to A4_REVIEW (manual). Never auto-print A4.
- Any PDF containing any Custom/unsupported page -> whole file goes to CUSTOM_REVIEW (manual).
- Long pages: if normalized page length > 3000mm -> whole file to CUSTOM_REVIEW (manual).
- Scale always 100%. Auto-rotate OFF. If rotation would be required -> CUSTOM_REVIEW.

## Execution safety
- Default execution mode is DRY_RUN.
- Real printing must require explicit config flag (EXECUTION_MODE=REAL) AND an explicit UI confirmation.
- Never delete anything except TEMP directories, and only after operator confirmation.

## Logging
- Append-only plain text log.
- One line per submitted page:
  timestamp | PLOTER=<queue> | COPIES=<n> | FILE=<original> | optional PAGE=<n>
- Log uses ORIGINAL file name (not temp file). PAGE only if source PDF was multi-page.

## Development rules
- Keep code Windows-compatible.
- Add tests for every pure function (classification, planning, validation).
- After changes run: `python -m pytest -q`.
