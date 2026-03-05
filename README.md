# Print Dispatch (Windows, PDF-only)

System półautomatycznego dispatchu wydruków wielkoformatowych:
- PDF-only
- Operator zatwierdza uruchomienie druku
- A4 nigdy nie jest drukowane automatycznie (A4_REVIEW)
- Custom/unsupported nigdy nie jest drukowane automatycznie (CUSTOM_REVIEW)
- Long: limit długości 3000 mm (ponad -> CUSTOM_REVIEW)
- Skala 100%, auto-rotate OFF
- 297 mm: load balancing paczkami po 5 stron na dwa plotery

## Plotery / kolejki Windows
- 297 mm: Ploter_A_297mm, Ploter_E_297mm
- 420 mm: Ploter_B_420mm
- T1300 (594/841): Ploter_C_594mm (jedna kolejka; profile wymuszają rolkę)

## Szybki start
1) Utwórz venv i zainstaluj zależności:
   - pytest, streamlit, pywin32, pypdf, reportlab
2) Uruchom testy:
   - `pytest -q`
3) Uruchom UI:
   - `streamlit run .\src\print_dispatch\ui\app_streamlit.py`

## Specyfikacje
Wszystkie reguły są w `spec/` i są kontraktem:
- dispatch_v1.md
- ui_contract_v1.md (z Manual Intake)
- validation_v1.md
- logging_v1.md
- manifest_schema_v1.md

## Codex workflow
- Pracuj milestone'ami (M0..M6a)
- Po każdym: `pytest -q` + commit
- Domyślnie DRY_RUN. REAL dopiero na końcu i za flagą.
