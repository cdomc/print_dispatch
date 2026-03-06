# Manifest Schema v1 (minimalny)

Manifest = jeden plik JSON per zlecenie.
Ma umożliwić UI odtworzenie:
- kafelka (osoba/temat/kopie/sposób opracowania + liczniki)
- list review (A4/CUSTOM)
- list automatu (grupy, paczki 297, FILE+PAGE+COPIES)
- statusy i błędy (retry)
- ścieżki persistent_dir i temp_dir

## 1. Order (wymagane)
- order_id: string (stabilny)
- received_time: string ISO lub "YYYY-MM-DD HH:MM:SS"
- source_type: "OUTLOOK" | "MANUAL"
- source_paths: [string]
- source_ref: string (OUTLOOK: entry id; MANUAL: "manual:<timestamp>")
- person: string
- topic: string
- copies_default: int >= 1
- sposob_opracowania: "Zeszyt" | "Teczka" | null
- state: "ZLECONE" | "W_TRAKCIE" | "WYDRUKOWANE" | "ZAKONCZONE"
- state_timestamps: map state->timestamp
- persistent_dir: string
- temp_dir: string | null

## 2. Review
review_items: list of:
- bucket: "A4_REVIEW" | "CUSTOM_REVIEW"
- file_original_name: string
- file_original_path: string
- reason: string (np. CONTAINS_A4, CONTAINS_CUSTOM_OR_UNSUPPORTED, PAGE_LENGTH_GT_3000, ROTATION_REQUIRED)

## 3. Printable pages (automat)
printable_pages: list of:
- file_original_name: string
- file_original_path: string
- page_number: int | null
- width_key: 297 | 420 | 594 | 841
- profile_id: string
- target_queue: string (po planowaniu; dla 297 po paczkowaniu)
- copies: int >= 1
- status: "PLANNED" | "SUBMITTED" | "FAILED"
- last_error: string | null

## 4. Groups
groups: list of:
- group_id: string
- target_queue: string
- profile_id: string
- item_refs: list of references to printable_pages (indexy lub ids)
- status: "READY" | "READY_WITH_CONFIRMATION" | "EXECUTING" | "COMPLETED" | "FAILED" | "BLOCKED"
- last_error: string | null
- confirmation_required: null | "ROLL_SELECTION"
- confirmation_state: null | "PENDING" | "CONFIRMED"

## 5. BatchPlan297 (opcjonalnie, jeśli są grupy 297)
batch_plan_297: object:
- K: 5
- qA: int
- qE: int
- start_printer: "Ploter_A_297mm" | "Ploter_E_297mm"
- batches: list of:
  - batch_index: int
  - target_queue: "Ploter_A_297mm" | "Ploter_E_297mm"
  - item_refs: list of printable_page refs
  - status: "READY" | "EXECUTING" | "COMPLETED" | "FAILED"
  - last_error: string | null

## 6. Execution history (minimalnie)
execution_attempts: list of:
- timestamp
- target: "group:<id>" | "batch:<index>"
- result: "OK" | "FAIL"
- error: string | null
