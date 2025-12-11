import google.generativeai as genai
import pandas as pd
import random
import streamlit as st

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            config = genai.types.GenerationConfig(
                temperature=0.9,
                top_p=0.95,
                candidate_count=1
            )
            return genai.GenerativeModel('models/gemini-1.5-flash', generation_config=config)
        else:
            return None
    except Exception as e:
        return None

model = init_ai()

# --- NARZĘDZIA ---
def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def process_message(raw_text):
    clean_text = usun_ogonki(raw_text)
    if len(clean_text) > 160:
        return clean_text[:157] + "..."
    return clean_text

# --- PARSOWANIE PLIKU VCF ---
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
                current["Ostatni Zabieg"] = "Import z pliku"
                contacts.append(current)
    return pd.DataFrame(contacts)

# --- GENEROWANIE WIADOMOŚCI (POPRAWIONE) ---
def generate_single_message_debug(salon_name, campaign_goal, client_name, last_treatment):
    """
    Zwraca krotkę: (wiadomość, prompt_użyty, błąd)
    Dzięki temu w UI zobaczymy co dokładnie wysłaliśmy do AI.
    """
    if not model:
        return None, None, "❌ Brak konfiguracji API KEY w secrets!"

    vibe_list = [
        "STYL: Przyjaciółka, dużo energii ✨",
        "STYL: Troskliwa i ciepła 🌿",
        "STYL: Konkretna i krótka 😎",
        "STYL: Ekskluzywna i elegancka 💎"
    ]
    current_vibe = random.choice(vibe_list)

    prompt = f"""
    Jesteś managerką salonu "{salon_name}". 
    Napisz SMS do klientki: "{client_name}".
    CEL KAMPANII: {campaign_goal}.
    OSTATNI ZABIEG: {last_treatment}.
    
    TWOJA ROLA: {current_vibe}
    
    ZASADY:
    1. Zacznij od WOŁACZA imienia (np. "Kasiu", "Marku").
    2. Max 160 znaków.
    3. Bez polskich znaków (usuń ogonki).
    4. Nie używaj słów "zapraszamy", "oferta".
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        res = model.generate_content(prompt, safety_settings=safety)
        if res.text:
            return process_message(res.text.strip()), prompt, None
        else:
            return None, prompt, "Pusta odpowiedź od AI"
    except Exception as e:
        return None, prompt, str(e)
