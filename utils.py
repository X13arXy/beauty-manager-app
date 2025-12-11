import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        return genai.GenerativeModel('models/gemini-1.5-flash')
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None

model = init_ai()

# --- NARZĘDZIA TECHNICZNE ---
def usun_ogonki(tekst):
    """Zamienia polskie znaki na łacińskie"""
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def process_message(raw_text):
    """Czyści tekst i pilnuje limitu"""
    clean_text = usun_ogonki(raw_text)
    if len(clean_text) > 160:
        return clean_text[:157] + "..."
    return clean_text

def generate_single_message(salon_name, campaign_goal, client_name, last_treatment):
    """Generuje wiadomość ze ścisłym trzymaniem się celu i odmianą imienia"""
    
    # PROMPT SKUPIONY NA CELU I GRAMATYCE
    prompt = f"""
    Jesteś copywriterem w salonie "{salon_name}".
    Masz napisać SMS do klienta: "{client_name}".
    
    WAŻNE - CEL KAMPANII: "{campaign_goal}".
    Musisz napisać DOKŁADNIE o tym celu. Nie pisz ogólników.
    
    INSTRUKCJA ODMIANY IMIENIA:
    1. Spójrz na pole klienta: "{client_name}".
    2. Jeśli to imię i nazwisko (np. Anna Nowak), weź TYLKO IMIĘ (Anna).
    3. Odmień to imię w WOŁACZU (np. "Czesc Aniu", "Czesc Krzysku", "Czesc Marku").
    4. Nigdy nie pisz "Witaj Anna" ani "Witaj Krzysiek". Ma być "Czesc Aniu", "Czesc Krzysku".
    
    ZASADY TECHNICZNE:
    1. Pisz bez polskich znaków (a, e, s, c, z...).
    2. Podpisz się: {salon_name}.
    3. Max 160 znaków.
    """
    
    # Wyłączenie filtrów
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Retry logic (3 próby)
        for _ in range(3):
            try:
                res = model.generate_content(prompt, safety_settings=safety)
                return process_message(res.text.strip())
            except:
                time.sleep(2) # Czekamy chwilę dłużej
        
        # AWARYJNIE (Jeśli AI nie odpowie):
        # Wstawiamy cel kampanii ręcznie, zamiast ogólnego "Zapraszamy"
        return usun_ogonki(f"Czesc {client_name.split()[0]}! {campaign_goal}. {salon_name}")
        
    except:
        # Ostateczna deska ratunku
        return usun_ogonki(f"Czesc! {campaign_goal}. {salon_name}")

# --- IMPORT Z TELEFONU ---
def parse_vcf(file_content):
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")
    contacts = []
    current = {}
    for line in content.splitlines():
        if line.startswith("BEGIN:VCARD"): current = {}
        elif line.startswith("FN:") or line.startswith("N:"):
            if "Imię" not in current:
                parts = line.split(":", 1)[1]
                current["Imię"] = parts.replace(";", " ").strip()
        elif line.startswith("TEL"):
            if "Telefon" not in current:
                num = line.split(":", 1)[1]
                clean = ''.join(filter(str.isdigit, num))
                if len(clean) == 9: clean = "48" + clean
                current["Telefon"] = clean
        elif line.startswith("END:VCARD"):
            if "Imię" in current and "Telefon" in current:
                current["Ostatni Zabieg"] = "Nieznany"
                contacts.append(current)
    return pd.DataFrame(contacts)
