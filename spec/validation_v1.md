# Validation Checklist v1

Walidacja działa na dwóch poziomach:
- przed udostępnieniem [Drukuj automatyczne]
- ponownie w momencie kliknięcia (środowisko: kolejki, qA/qE, bramka rolki C)

## 1. Walidacje plikowe (twarde, mają pierwszeństwo)
Dla każdego PDF:
1) Dostępność: plik istnieje i jest czytelny.
   - jeśli nie: CUSTOM_REVIEW (MISSING_OR_UNREADABLE_FILE)
2) A4: jeśli jakakolwiek strona A4 -> cały plik do A4_REVIEW (CONTAINS_A4)
3) Custom/unsupported: jeśli jakakolwiek strona custom lub unsupported width -> cały plik do CUSTOM_REVIEW (CONTAINS_CUSTOM_OR_UNSUPPORTED)

Tylko pliki bez A4 i bez Custom idą dalej.

## 2. Walidacje stron (dla plików dopuszczonych)
Po normalizacji orientacji:
- width_key musi być jedną z: 297, 420, 594, 841 (w tolerancji)
- Standard dozwolony tylko: A3 (297x420)

Long:
- jeśli length_mm > 3000 -> cały plik do CUSTOM_REVIEW (PAGE_LENGTH_GT_3000)

Rotacja:
- auto-rotate OFF
- jeśli wykryto, że strona wymaga rotacji -> cały plik do CUSTOM_REVIEW (ROTATION_REQUIRED)

## 3. Walidacje routingu i profili
- Dla każdej strony musi istnieć mapowanie width_key -> queue i profile_id.
- Jeśli brak -> BLOCKED (NO_ROUTING_RULE) i traktuj jak manual (CUSTOM_REVIEW).

## 4. Walidacje środowiska (w momencie commit)
- Kolejki muszą istnieć:
  Ploter_A_297mm, Ploter_E_297mm, Ploter_B_420mm, Ploter_C_594mm
  - jeśli brak -> odpowiednie grupy BLOCKED (MISSING_PRINTER_QUEUE)

- 297: odczyt qA/qE:
  - jeśli się nie uda: fallback deterministyczny qA=qE=0, start=A
  - log: QUEUE_DEPTH_UNAVAILABLE

- Ploter C: deterministyczność rolki:
  - jeśli profil może wymusić rolkę 594/841 -> READY
  - jeśli nie -> READY_WITH_CONFIRMATION: ROLL_SELECTION (UI musi potwierdzić)

## 5. Kryterium "wydrukowane" (v1)
- COMPLETED = submit OK do kolejki drukarki (nie potwierdzamy fizycznego wydruku).
- Zlecenie przechodzi W_TRAKCIE->WYDRUKOWANE gdy wszystkie automatyczne elementy są COMPLETED.
- Operator domyka fizycznie: WYDRUKOWANE->ZAKONCZONE.
