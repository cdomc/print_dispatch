import win32com.client
import json
import os
import re
import shutil
from datetime import datetime
import sys
import atexit
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter
import configparser
import logging
import itertools

# --- Kolory dla komunikatów w konsoli ---
os.system("") # Aktywuje obsługę kolorów w terminalu Windows
KOLOR_CZERWONY = "\033[91m"
KOLOR_ZIELONY = "\033[92m"
KOLOR_ZOLTY = "\033[93m"
KOLOR_RESET = "\033[0m"

# --- Konfiguracja Logowania ---
def setup_logging():
    """Konfiguruje logowanie do konsoli (z kolorami) i do pliku."""
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    console_formatter = logging.Formatter('%(message)s')

    try:
        file_handler = logging.FileHandler('historia działania.log', encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"{KOLOR_CZERWONY}Nie udało się utworzyć pliku logu: {e}{KOLOR_RESET}")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

# --- Konfiguracja ---
PROCESSED_IDS_FILE = "processed_ids.json"
BASE_DEST = r"Z:\!Druk_skrypt"
TOLERANCE = 2
LOCK_FILE = None
STANDARD_FORMATS = {"A3": (297, 420), "A4": (210, 297)}
LONG_FORMATS = {"A0_long": 841, "A1_long": 594, "A2_long": 420, "A3_long": 297}

# --- Helper functions ---
def resolve_base_dest():
    p = BASE_DEST
    try:
        os.makedirs(p, exist_ok=True)
        test_path = os.path.join(p, "_rw_test.tmp")
        with open(test_path, "w", encoding="utf-8") as tf:
            tf.write("ok")
        os.remove(test_path)
        return p
    except Exception as e:
        raise RuntimeError(f"Brak dostępu do lokalizacji docelowej {p}. Sprawdź mapowanie Z:. Błąd: {e}")

_lock_fd = None
def acquire_lock(lock_file_path):
    global _lock_fd
    try:
        _lock_fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(_lock_fd, f"PID={os.getpid()}".encode("utf-8"))
        return True
    except FileExistsError:
        return False
    except Exception:
        return True

def release_lock(lock_file_path):
    global _lock_fd
    try:
        if _lock_fd is not None:
            os.close(_lock_fd)
            _lock_fd = None
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)
    except Exception:
        pass

def load_processed_ids(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_processed_ids(ids_set, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(ids_set), f, ensure_ascii=False, indent=2)

_def_forbidden = re.compile(r'[<>:"/\\|?*\r\n]+')
_def_spaces = re.compile(r'\s+')
def safe_name(txt: str, maxlen: int = 64) -> str:
    s = (txt or '').strip()
    s = _def_forbidden.sub('_', s)
    s = _def_spaces.sub('_', s)
    return s[:maxlen].rstrip('_') if len(s) > maxlen else s

def get_order_prefix(index: int) -> str:
    """Generuje prefiks literowy na podstawie indeksu (1 -> A_, 2 -> B_, ..., 27 -> AA_)."""
    if not isinstance(index, int) or index <= 0:
        return "" 
    chars = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        chars.append(chr(65 + remainder))
    return "".join(reversed(chars)) + "_"

def ensure_category(ns, name="Processed"):
    try:
        cats = ns.Application.Session.Categories
        if not any(cat.Name == name for cat in cats):
            cats.Add(name)
    except Exception:
        pass

def mark_processed(msg, ns):
    try:
        ensure_category(ns, "Processed")
        categories = msg.Categories or ""
        if "Processed" not in categories.split(';'):
            msg.Categories = f"{categories};Processed".strip(';')
        msg.UnRead = False
        msg.Save()
        return True
    except Exception:
        return False

def parse_paths_field(raw):
    s = (raw or '').strip()
    if not s: return []
    if s.startswith('[') and s.endswith(']'):
        return re.findall(r'["\']([^"\']+)["\']', s) or [p.strip() for p in s[1:-1].split(';') if p.strip()]
    return [p.strip() for p in re.split(r'[;\n\r]+', s) if p.strip()]

def parse_email_body(body):
    patterns = {
        'topic_name': r"Nazwa tematu.*?\[([^\]]+)\]",
        'doc_type': r"Rodzaj drukowanego dokumentu.*?\[([^\]]+)\]",
        'person': r"osoba zlecająca i odpowiedzialna.*?\[([^\]]+)\]",
        'copies': r"ilość egzemplarzy.*?\[([^\]]+)\]",
    }
    result = {key: (m.group(1).strip() if (m := re.search(pat, body, re.IGNORECASE | re.DOTALL)) else None) for key, pat in patterns.items()}
    path_match = re.search(r"ścieżka zawierająca folder z pdf.*?\[([^\]]+)\]", body, re.IGNORECASE | re.DOTALL)
    result['paths'] = parse_paths_field(path_match.group(1).strip() if path_match else None)
    return result

def fetch_outlook_emails(log):
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    except Exception:
        log.error(f"{KOLOR_CZERWONY}BŁĄD: Nie można połączyć się z aplikacją Microsoft Outlook.{KOLOR_RESET}")
        log.warning("Upewnij się, że Outlook jest uruchomiony i poprawnie skonfigurowany.")
        return []

    processed_ids = load_processed_ids(PROCESSED_IDS_FILE)
    store = None
    target_account = "ploterownia@value-eng.pl"
    try:
        for st in outlook.Folders:
            if target_account.lower() in st.Name.lower():
                store = st
                break
    except Exception as e:
        if "Brak połączenia" in str(e) or "-2147352567" in str(e):
            log.error(f"{KOLOR_CZERWONY}BŁĄD: Outlook nie jest połączony z serwerem pocztowym.{KOLOR_RESET}")
            log.warning(f"{KOLOR_ZOLTY}Sprawdź status połączenia w Outlooku i upewnij się, że nie pracujesz w trybie offline.{KOLOR_RESET}")
        else:
            log.error(f"{KOLOR_CZERWONY}Wystąpił nieoczekiwany błąd podczas dostępu do folderów Outlooka.{KOLOR_RESET}", exc_info=True)
        return []
    
    if not store:
        log.error(f"{KOLOR_CZERWONY}Nie znaleziono konta '{target_account}' w Outlooku.{KOLOR_RESET}")
        return []

    try:
        inbox = store.Folders("Inbox")
    except Exception:
        try:
            inbox = store.Folders("Skrzynka odbiorcza")
        except Exception:
            log.error(f"{KOLOR_CZERWONY}Nie można znaleźć folderu 'Inbox' ani 'Skrzynka odbiorcza' w '{store.Name}'.{KOLOR_RESET}")
            return []

    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    orders = []
    subject_keyword = "Nowe_Zlecenie_Wydruku_123"
    for msg in messages:
        try:
            if subject_keyword.lower() not in (msg.Subject or "").lower():
                continue
            if msg.EntryID in processed_ids:
                mark_processed(msg, outlook)
                continue
            body = msg.Body or ""
            data = parse_email_body(body)
            data['body'], data['received'], data['entry_id'] = body, msg.ReceivedTime.strftime("%Y-%m-%d %H:%M:%S"), msg.EntryID
            orders.append(data)
        except Exception as e:
            log.warning(f"Problem z przetwarzaniem maila: {msg.Subject}. Błąd: {e}")
    
    new_ids = {order['entry_id'] for order in orders}
    if new_ids:
        save_processed_ids(processed_ids.union(new_ids), PROCESSED_IDS_FILE)
        for order in orders:
             try:
                msg_to_mark = outlook.GetItemFromID(order['entry_id'])
                mark_processed(msg_to_mark, outlook)
             except Exception:
                log.warning(f"Nie udało się oznaczyć maila {order['entry_id']} jako przetworzony.")

    return orders

def unique_path(dest_dir: str, filename: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dest_dir, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{base}_{i:02d}{ext}")
        i += 1
    return candidate

def safe_copy(src: str, dest_dir: str, new_filename: str = None) -> str:
    filename = new_filename if new_filename else os.path.basename(src)
    dest = unique_path(dest_dir, filename)
    shutil.copy2(src, dest)
    return dest

def safe_move(src: str, dest_dir: str) -> str:
    dest = unique_path(dest_dir, os.path.basename(src))
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.move(src, dest)
    return dest

def copy_pdfs_for_order(order, base_dest, log):
    paths = order.get('paths', [])
    person = safe_name(order.get('person', 'unknown'), 40)
    topic = safe_name(order.get('topic_name', ''), 60)
    doc_tp = safe_name(order.get('doc_type', ''), 40)
    recv_dt = datetime.strptime(order['received'], "%Y-%m-%d %H:%M:%S")
    date_folder = recv_dt.strftime("%y%m%d")
    time_folder = recv_dt.strftime("%H%M%S")

    dest_root = os.path.join(base_dest, date_folder)
    dest_folder_name = f"{time_folder}_{person}_{topic}_{doc_tp}".strip('_')
    if len(dest_folder_name) > 120:
        dest_folder_name = dest_folder_name[:120].rstrip('_')
    
    dest_folder = os.path.join(dest_root, dest_folder_name)
    os.makedirs(dest_folder, exist_ok=True)

    with open(os.path.join(dest_folder, 'email_body.txt'), 'w', encoding='utf-8') as tf:
        tf.write(order['body'])

    stats = {"pdf_copied": 0, "doc_copied": 0, "unavailable_paths": 0}
    for idx, src_dir in enumerate(paths, start=1):
        if not src_dir: continue

        path_prefix = get_order_prefix(idx)
        src_norm = os.path.normpath(src_dir.strip().strip('"').strip("'"))
        
        def create_shortcut(target_path: str, label_base: str):
            try:
                shell = win32com.client.Dispatch('WScript.Shell')
                base = safe_name(label_base, 40) or f"PATH{idx:02d}"
                lnk_path = os.path.join(dest_folder, f"Link_{idx:02d}_{base}.lnk")
                shortcut = shell.CreateShortcut(lnk_path)
                shortcut.TargetPath = target_path
                shortcut.WorkingDirectory = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
                shortcut.save()
            except Exception:
                log.warning(f"Nie udało się utworzyć skrótu do: {target_path}")

        if os.path.isdir(src_norm):
            safe_base = safe_name(os.path.basename(src_norm) or f'PATH{idx:02d}', 40)
            create_shortcut(src_norm, safe_base)
            
            subfolder_map = {}
            subfolder_idx = 0
            
            # Użycie sorted() gwarantuje, że podfoldery zawsze dostaną te same litery (w porządku alfabetycznym)
            for root, _, files in sorted(os.walk(src_norm)):
                relative_path = os.path.relpath(root, src_norm)
                subfolder_prefix = ""

                # Jeśli plik jest w podfolderze (a nie w folderze głównym ścieżki)
                if relative_path != ".":
                    # Jeśli ten podfolder jest nowy, przypisz mu kolejną małą literę
                    if relative_path not in subfolder_map:
                        subfolder_idx += 1
                        # Używamy a-z, a potem przechodzimy na liczby, jeśli jest bardzo dużo podfolderów
                        if subfolder_idx <= 26:
                            subfolder_map[relative_path] = f"{chr(96 + subfolder_idx)}_" # a, b, c...
                        else:
                            subfolder_map[relative_path] = f"{subfolder_idx}_"
                    
                    subfolder_prefix = subfolder_map[relative_path]

                for f in files:
                    fl = f.lower()
                    if fl.endswith(('.pdf', '.doc', '.docx')):
                        final_prefixed_name = f"{path_prefix}{subfolder_prefix}{f}"
                        safe_copy(os.path.join(root, f), dest_folder, new_filename=final_prefixed_name)
                        if fl.endswith('.pdf'):
                            stats["pdf_copied"] += 1
                        else:
                            stats["doc_copied"] += 1
        
        elif os.path.isfile(src_norm):
            safe_base = safe_name(os.path.splitext(os.path.basename(src_norm))[0] or f'FILE{idx:02d}', 40)
            create_shortcut(src_norm, safe_base)
            ext_l = os.path.splitext(src_norm)[1].lower()
            if ext_l in ('.pdf', '.doc', '.docx'):
                original_filename = os.path.basename(src_norm)
                final_prefixed_name = f"{path_prefix}{original_filename}"
                safe_copy(src_norm, dest_folder, new_filename=final_prefixed_name)
                if ext_l == '.pdf':
                    stats["pdf_copied"] += 1
                else:
                    stats["doc_copied"] += 1
        
        else:
            stats["unavailable_paths"] += 1
            log.warning(f"{KOLOR_CZERWONY}Ścieżka niedostępna lub nie istnieje: {src_norm}{KOLOR_RESET}")
            create_shortcut(src_norm, os.path.basename(src_norm) or f'PATH_niedostepny_{idx:02d}')
            
    return dest_folder, stats

def pt_to_mm(pt): return float(pt) * 25.4 / 72

def detect_format(w_mm, h_mm):
    orient = 'pionowa' if h_mm >= w_mm else 'pozioma'
    if orient == 'pozioma': w_mm, h_mm = h_mm, w_mm
    rw, rh = round(w_mm), round(h_mm)
    for name, (w, h) in STANDARD_FORMATS.items():
        if abs(rw - w) <= TOLERANCE and abs(rh - h) <= TOLERANCE: return name, orient
    for name, ew in LONG_FORMATS.items():
        if abs(rw - ew) <= TOLERANCE: return name, orient
    return f"Custom:{rw}x{rh}", orient

def extract_and_sort(order_folder, order_data, log):
    records, custom_warnings = [], []
    stats = {"word_moved": 0, "pdf_files_processed": 0, "pdf_pages_total": 0, "packages_generated": 0, "single_pdf_moved": 0, "custom_pages": 0}
    
    try:
        copies_str = order_data.get('copies', '1') or '1'
        num_copies = int(re.search(r'\d+', copies_str).group())
    except (ValueError, AttributeError):
        num_copies = 1

    words_folder = os.path.join(order_folder, 'WORD')
    
    all_files = []
    for root, _, files in os.walk(order_folder):
        if os.path.basename(root) in list(STANDARD_FORMATS.keys()) + list(LONG_FORMATS.keys()) + ['WORD', '_oryginal']:
            continue
        for f in files:
            all_files.append((root, f))
            
    for root, f in all_files:
        pth = os.path.join(root, f)
        fl = f.lower()
        if fl.endswith(('.doc', '.docx')):
            os.makedirs(words_folder, exist_ok=True)
            safe_move(pth, words_folder)
            stats["word_moved"] += 1
            continue
        if not fl.endswith('.pdf'): continue
        
        try:
            rdr = PdfReader(pth)
            num_pages = len(rdr.pages)
            stats["pdf_files_processed"] += 1; stats["pdf_pages_total"] += num_pages
            page_info = []
            for i, pg in enumerate(rdr.pages):
                w_mm, h_mm = pt_to_mm(pg.mediabox.width), pt_to_mm(pg.mediabox.height)
                fmt, ori = detect_format(w_mm, h_mm)
                if fmt.startswith('Custom:'): 
                    custom_warnings.append((f, round(w_mm, 1), round(h_mm, 1), i + 1))
                    stats["custom_pages"] += 1
                
                page_info.append({'fmt_name': fmt.split(':')[0], 'w': round(w_mm, 1), 'h': round(h_mm, 1), 'fmt': fmt, 'ori': ori})
                
                area = page_info[-1]['w'] * page_info[-1]['h']
                records.append({
                    'Plik': f, 'Strona': i + 1, 'Ilość kopii': num_copies, 
                    'Szer(mm)': page_info[-1]['w'], 'Wys(mm)': page_info[-1]['h'], 
                    'Pole pliku (mm^2)': area, 'Calkowite pole (mm^2)': area * num_copies, 
                    'Format': fmt, 'Orientacja': ori, 'Ścieżka': pth
                })
            
            unique_fmt_names = {pi['fmt_name'] for pi in page_info}
            if len(unique_fmt_names) == 1:
                fmt_folder = list(unique_fmt_names)[0]
                tgt = os.path.join(order_folder, fmt_folder)
                os.makedirs(tgt, exist_ok=True)
                safe_move(pth, tgt)
                stats["single_pdf_moved"] += 1
            else:
                base, _ = os.path.splitext(f)
                split_root = os.path.join(order_folder, base)
                orig_dir = os.path.join(split_root, '_oryginal')
                os.makedirs(orig_dir, exist_ok=True)
                safe_move(pth, orig_dir)

                indexed_page_info = enumerate(page_info)
                for fmt_name, group in itertools.groupby(indexed_page_info, key=lambda item: item[1]['fmt_name']):
                    writer = PdfWriter()
                    block = list(group)
                    page_indices = [item[0] for item in block]

                    for page_index in page_indices:
                        writer.add_page(rdr.pages[page_index])
                    
                    fmt_folder = os.path.join(split_root, fmt_name)
                    os.makedirs(fmt_folder, exist_ok=True)
                    
                    if len(page_indices) == 1:
                        str_indices = f"strona_{page_indices[0] + 1}"
                    else:
                        str_indices = f"strony_{page_indices[0] + 1}-{page_indices[-1] + 1}"
                    
                    out_name = f"{base}__{fmt_name}_{str_indices}.pdf"
                    out_path = unique_path(fmt_folder, out_name)
                    with open(out_path, 'wb') as w:
                        writer.write(w)
                    stats["packages_generated"] += 1

        except Exception as e:
            log.error(f"Błąd przetwarzania PDF {pth}: {e}", exc_info=True)
    
    if custom_warnings:
        log.warning(f"{KOLOR_ZOLTY}Wykryto strony o niestandardowych wymiarach:{KOLOR_RESET}")
        for fname, w, h, pnum in custom_warnings:
            log.warning(f" - {fname}, str. {pnum}: {w}x{h}mm")

    coefficient = 0.0
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0] if hasattr(sys, 'frozen') else __file__))
        coeff_path = os.path.join(script_dir, 'wspolczynnik.txt')
        if os.path.exists(coeff_path):
            with open(coeff_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    content = content.replace(',', '.')
                    coefficient = float(content)
        else:
            log.warning(f"{KOLOR_CZERWONY}Plik 'wspolczynnik' nie został znaleziony. Czas wydruku nie zostanie obliczony.{KOLOR_RESET}")
    except (ValueError, TypeError):
        log.error(f"{KOLOR_CZERWONY}Błąd odczytu pliku 'wspolczynnik'. Upewnij się, że zawiera poprawną liczbę.{KOLOR_RESET}")
        coefficient = 0.0
    
    if records:
        df = pd.DataFrame(records)
        column_order = ['Plik', 'Strona', 'Ilość kopii', 'Szer(mm)', 'Wys(mm)', 'Pole pliku (mm^2)', 'Calkowite pole (mm^2)', 'Format', 'Orientacja', 'Ścieżka']
        df = df[column_order]
        report_path = os.path.join(order_folder, 'formaty_papieru_mm.xlsx')
        try:
            with pd.ExcelWriter(report_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Raport')
                workbook, worksheet = writer.book, writer.sheets['Raport']
                
                yellow_bold = workbook.add_format({'bold': True, 'bg_color': '#FFFF00'})
                yellow_num = workbook.add_format({'num_format': '0.0000', 'bg_color': '#FFFF00'})
                time_format = workbook.add_format({'num_format': '0.00', 'bg_color': '#FFFF00'})
                
                if not df.empty:
                    worksheet.write('K1', 'Suma całkowita (m^2):', yellow_bold)
                    worksheet.write_formula('L1', f'=SUM(G2:G{len(df) + 1})/1000000', yellow_num)
                    
                    if coefficient > 0:
                        worksheet.write('K2', 'Prognozowany czas wydruku (min):', yellow_bold)
                        worksheet.write_formula('L2', f'=L1*{coefficient}', time_format)

                # Pętla do automatycznego dopasowania szerokości kolumn
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, max_len)
                
                worksheet.set_column(9, 9, 30) 
            
                
                worksheet.set_column('K:K', 30)
                worksheet.set_column('L:L', 20)
            log.info(f"Raport zapisany: {report_path}")
        except Exception as e:
            log.error(f"{KOLOR_CZERWONY}Nie udało się zapisać raportu Excel: {e}{KOLOR_RESET}", exc_info=True)
    else:
        log.warning(f"{KOLOR_ZOLTY}Brak PDF-ów do raportu w {order_folder}{KOLOR_RESET}")

    return stats


def main():
    """Główna funkcja wykonawcza skryptu."""
    log = setup_logging()
    
    global LOCK_FILE
    try:
        DEST_BASE = resolve_base_dest()
        LOCK_FILE = os.path.join(DEST_BASE, "_script_running.lock")
        atexit.register(release_lock, LOCK_FILE)
    except Exception as e:
        log.error(f"{KOLOR_CZERWONY}Błąd krytyczny przy ustawianiu ścieżki docelowej: {e}{KOLOR_RESET}", exc_info=True)
        return

    if not acquire_lock(LOCK_FILE):
        log.warning(f"{KOLOR_ZOLTY}Skrypt już działa (wykryto blokadę). Kończę to wywołanie.{KOLOR_RESET}")
        return

    try:
        log.info("Uruchamianie skryptu Python...")
        orders = fetch_outlook_emails(log)
        if not orders:
            log.info(f"{KOLOR_ZIELONY}Brak nowych maili.{KOLOR_RESET}")
        else:
            today_folder = datetime.now().strftime("%y%m%d")
            log.info(f"Przetwarzam {len(orders)} zleceń...")
            for order in orders:
                try:
                    folder, copy_stats = copy_pdfs_for_order(order, DEST_BASE, log)
                    log.info(f"Skopiowano do {folder}")
                    
                    recv_folder = datetime.strptime(order['received'], "%Y-%m-%d %H:%M:%S").strftime("%y%m%d")
                    if recv_folder != today_folder:
                        log.warning(f"{KOLOR_ZOLTY}Uwaga: zamówienie z datą {recv_folder}, inną niż dzisiejsza ({today_folder})!{KOLOR_RESET}")

                    sort_stats = extract_and_sort(folder, order, log)

                    log.info("— Podsumowanie tego zlecenia —")
                    log.info(f"Pliki skopiowane: PDF({copy_stats['pdf_copied']}), DOC/DOCX({copy_stats['doc_copied']}). Ścieżki niedostępne: {copy_stats['unavailable_paths']}")
                    log.info(f"PDF przetworzone: {sort_stats['pdf_files_processed']} (stron: {sort_stats['pdf_pages_total']}). Ostrzeżenia o formacie: {sort_stats['custom_pages']}")
                except Exception as e:
                    log.error(f"{KOLOR_CZERWONY}Nie udało się przetworzyć zlecenia z maila o ID {order.get('entry_id')}.{KOLOR_RESET}", exc_info=True)

            log.info(f"{KOLOR_ZIELONY}Sortowanie i raporty gotowe dla wszystkich zamówień.{KOLOR_RESET}")
            
    except Exception as e:
        log.error(f"{KOLOR_CZERWONY}Wystąpił nieprzewidziany błąd krytyczny w głównej pętli skryptu.{KOLOR_RESET}", exc_info=True)
    finally:
        log.info("Skrypt zakończył działanie.")
        release_lock(LOCK_FILE)

if __name__ == "__main__":
    main()