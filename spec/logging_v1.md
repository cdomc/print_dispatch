# Logging v1 (plain text)

Log jest append-only.

## 1. Jedna linia na jeden zlecony druk (jedna strona)
Logujemy w momencie SUBMIT do kolejki drukarki.

## 2. Minimalne pola
- timestamp (data+godzina)
- ploter (nazwa kolejki Windows)
- copies
- original FILE (nazwa oryginalnego PDF)
- PAGE tylko jeśli źródło było wielostronicowe

## 3. Format
Single-page źródło:
YYYY-MM-DD HH:MM:SS | PLOTER=<queue> | COPIES=<n> | FILE=<original.pdf>

Multi-page źródło:
YYYY-MM-DD HH:MM:SS | PLOTER=<queue> | COPIES=<n> | FILE=<original.pdf> | PAGE=<n>

Przykład:
2026-02-20 14:23:11 | PLOTER=Ploter_A_297mm | COPIES=2 | FILE=Projekt_Zjazdy.pdf | PAGE=3
