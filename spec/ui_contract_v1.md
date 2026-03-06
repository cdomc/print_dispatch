# UI Contract v1

## 1. Widok główny
4 kolumny (kanban):
- Zlecone
- W trakcie
- Wydrukowane
- Zakończone (możliwe usunięcie TEMP po autoryzacji)

Kafelki reprezentują ZLECENIA (Order), które mogą zawierać wiele formatów i wiele grup druku.

## 2. Kafelek zlecenia — pola
Na kafelku:
- Osoba
- Temat
- Kopie (domyślne)
- Sposób opracowania: Zeszyt / Teczka / (brak)
- Podsumowanie:
  - A4_REVIEW: X plików
  - CUSTOM_REVIEW: Y plików
  - Auto 297 A3: N stron
  - Auto 297 A3Long: M stron
  - Auto 420 Long: ...
  - Auto 594 Long: ...
  - Auto 841 Long: ...
- (opcjonalnie) Szac. czas: może być "—" w v1

## 3. Akcje na kafelku
Zależnie od stanu i zawartości:
- [Drukuj automatyczne] (tylko jeśli są elementy wykonawcze automatu)
- [Otwórz A4_REVIEW] (jeśli X>0)
- [Otwórz CUSTOM_REVIEW] (jeśli Y>0)
- [Szczegóły] (zawsze)

UI nie pokazuje przycisku, który pozwoli drukować A4 lub Custom automatycznie.

## 4. Szczegóły zlecenia
Sekcje:

### 4.1 Review (manual)
- Lista plików w A4_REVIEW wraz z powodem (CONTAINS_A4).
- Lista plików w CUSTOM_REVIEW wraz z powodem (CONTAINS_CUSTOM_OR_UNSUPPORTED / PAGE_LENGTH_GT_3000 / ROTATION_REQUIRED / itp.).
Akcje: [Otwórz plik] / [Otwórz folder].

### 4.2 Automat — grupy druku
Grupy wg (ploter + profil). Dla każdej grupy:
- docelowa kolejka (queue)
- profil (profile_id)
- liczba stron
- status: READY / EXECUTING / COMPLETED / FAILED / READY_WITH_CONFIRMATION
- lista pozycji: FILE + (PAGE jeśli multi) + COPIES

### 4.3 Plan 297 (paczki)
Dla grup 297 osobno:
- qA, qE, start, K=5 (zamrożone w momencie kliknięcia)
- paczki: docelowy ploter A/E + lista pozycji (FILE+PAGE+COPIES)

## 5. Przejścia stanów zlecenia
- Zlecone -> W trakcie: po kliknięciu [Drukuj automatyczne] (plan zamrożony).
- W trakcie -> Wydrukowane: gdy wszystkie automatyczne grupy/paczki mają COMPLETED (v1 = submit OK).
- Wydrukowane -> Zakończone: po kliknięciu [Potwierdź zakończenie] (blokuj jeśli sposób opracowania = (brak)).
- Zakończone: dostępne [Usuń TEMP] z autoryzacją.

## 6. Ploter C — bramka potwierdzenia rolki (fallback)
Jeśli grupa C ma status READY_WITH_CONFIRMATION: ROLL_SELECTION:
- UI zatrzymuje wykonanie przed tą grupą.
- UI wymaga kliknięcia [Kontynuuj] / [Wstrzymaj], pokazując wymaganą szerokość rolki (594 lub 841).

## 7. Usuwanie TEMP
- Dostępne tylko w Zakończone.
- Wymaga potwierdzenia operatora (modal).
- Usuwa tylko temp_dir, nie usuwa logów ani folderów review.

## 8. Manual Intake (Szybkie zlecenie)
UI ma w nagłówku przycisk: [Nowe zlecenie ręczne].

Formularz:
- Ścieżka (wymagana): folder lub plik
- Kopie (wymagane): int >= 1
- Osoba (opcjonalnie, domyślnie "Ręczne")
- Temat (opcjonalnie, domyślnie "Ręczne")
- Sposób opracowania (opcjonalnie): Zeszyt/Teczka/(brak)

Akcje:
- [Utwórz zlecenie] -> tworzy kafelek w Zlecone i uruchamia prepare/analizę.
- [Utwórz i drukuj automatyczne] -> jak wyżej + natychmiast commit (Zlecone->W trakcie).

Manual Intake tworzy zlecenie o source_type=MANUAL, ale pipeline jest identyczny jak dla OUTLOOK.
