# Dispatch v1 (kontrakt)

## 1. Nadrzędne reguły plikowe (review blokuje automat)
Dla każdego PDF:
1) Jeśli PDF zawiera jakąkolwiek stronę A4 -> CAŁY plik do A4_REVIEW (manual, non-executable).
2) Jeśli PDF zawiera jakąkolwiek stronę Custom/unsupported -> CAŁY plik do CUSTOM_REVIEW (manual, non-executable).

Tylko pliki, które nie spełniają (1) ani (2), wchodzą do automatu.

## 2. Formaty wykonywalne
- Standard: tylko A3 (297x420).
- Long: szerokości 297/420/594/841, cięcie per strona (każda strona osobno).
- Skala: 100%.
- Auto-rotate: OFF.

## 3. Limit long 3000 mm (twardy)
Jeśli jakakolwiek strona long (po normalizacji) ma length_mm > 3000:
- CAŁY plik do CUSTOM_REVIEW z powodem PAGE_LENGTH_GT_3000.

## 4. Rotacja (twardy blok)
Jeśli jakakolwiek strona wymagałaby rotacji, by pasować do docelowej szerokości:
- CAŁY plik do CUSTOM_REVIEW z powodem ROTATION_REQUIRED.

## 5. Routing (width -> queue)
- 297 -> Ploter_A_297mm lub Ploter_E_297mm (balans paczkami po 5 stron).
- 420 -> Ploter_B_420mm (automatycznie).
- 594 -> Ploter_C_594mm (profil wymusza rolkę 594).
- 841 -> Ploter_C_594mm (profil wymusza rolkę 841).

## 6. Profile (ID -> zachowanie)
- P297_A3_STD: A3 standard, bez remove trailing blank.
- P297_A3_LONG_3000_TRIM: long max 3000 + remove trailing blank ON.
- P420_A2_LONG_3000_TRIM: long max 3000 + remove trailing blank ON.
- P594_A1_LONG_3000_TRIM: long max 3000 + remove trailing blank ON + rolka 594 wymuszona.
- P841_A0_LONG_3000_TRIM: long max 3000 + remove trailing blank ON + rolka 841 wymuszona.

## 7. Planowanie 297 (A/E) — paczki po 5 stron
Dotyczy osobno grup:
- 297 + A3_STD
- 297 + A3_LONG_3000_TRIM

Definicja:
- qA, qE = liczba zleconych druków (stron) na dany ploter w momencie kliknięcia "Drukuj automatyczne".
- K = 5 stron na paczkę.

Algorytm:
1) Odczytaj qA i qE.
2) Start = ploter z mniejszym q; remis -> start=A.
3) Posortuj strony deterministycznie (original_name + page_number).
4) Podziel na paczki po 5 stron.
5) Przydziel paczki naprzemiennie: 1->start, 2->drugi, 3->start, ...
6) Kopie strony zawsze na tym samym ploterze co strona (nie rozdzielać kopii).

UI i log mają pokazywać listy plików/stron w paczkach.

## 8. Ploter C (594/841) — deterministyczność rolki
- System NIE może polegać na autodetect jako cichej heurystyce.
- Jeżeli profil potrafi wymusić rolkę -> automatycznie.
- Jeżeli nie potrafi -> grupa ma stan READY_WITH_CONFIRMATION: ROLL_SELECTION i wymaga jawnego potwierdzenia operatora przed wysyłką.

## 9. Kolejność wykonania po kliknięciu "Drukuj automatyczne"
Stała sekwencja:
1) 297 A3_STD (paczki A/E)
2) 297 A3_LONG (paczki A/E)
3) 420 LONG (B)
4) 594 LONG (C)
5) 841 LONG (C)

## 10. TEMP vs persistent
- TEMP: pliki robocze (single-page) + artefakty wykonawcze; usuwalne po autoryzacji.
- Persistent: folder zlecenia, A4_REVIEW, CUSTOM_REVIEW, logi.
