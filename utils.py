import google.generativeai as genai
import pandas as pd
import time
import random
import streamlit as st

# --- 1. KONFIGURACJA AI ---
def init_ai():
    try:
        # Pobieramy klucz z sekretów Streamlit
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # Ustawiamy parametry kreatywności
        config = genai.types.GenerationConfig(
            temperature=0.9, # Wysoka kreatywność
            top_p=0.95,
            candidate_count=1
        )
        return genai.GenerativeModel('models/gemini-1.5-flash', generation_config=config)
    except Exception as e:
        # Jeśli nie ma klucza lub jest błąd, zwracamy None
        return None

model = init_ai()

# --- 2. FUNKCJE POMOCNICZE (TEKST) ---
def usun_ogonki(tekst):
    """Zamienia polskie znaki na łacińskie (np. ą -> a, ś -> s)"""
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def process_message(raw_text):
    """Czyści tekst i przycina do długości SMS"""
    clean_text = usun_ogonki(raw_text)
    if len(clean_text) > 160:
        return clean_text[:157] + "..."
    return clean_text

# --- 3. GENEROWANIE WIADOMOŚCI (AI) ---
def generate_single_message(salon_name, campaign_goal, client_name, last_treatment):
    # Lista stylów, żeby wiadomości nie były takie same
    vibe_list = [
        "STYL: Przyjaciółka, dużo energii, emoji ✨. Bez oficjalnego tonu!",
        "STYL: Troskliwa, ciepła, nacisk na relaks 🌿. Spokojny ton.",
        "STYL: Konkretna, krótka, z humorem 😎. Krótka piłka.",
        "STYL: Ekskluzywna, elegancka 💎."
    ]
    current_vibe = random.choice(vibe_list)

    prompt = f"""
    Jesteś managerką salonu "{salon_name}". Napisz SMS do: "{client_name}".
    CEL: {campaign_goal}.
    Ostatni zabieg: {last_treatment}.
    STYL: {current_vibe}
    ZASADY:
    1. Użyj wołacza (np. "Aniu").
    2. Max 160 znaków.
    3. Bez polskich znaków (usuń ogonki).
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Próba generowania przez AI
        if model:
            res = model.generate_content(prompt, safety_settings=safety)
            return process_message(res.text.strip())
        else:
            raise Exception("Model AI nie został załadowany")
            
    except Exception as e:
        print(f"Błąd AI (fallback): {e}")
        # Wiadomość awaryjna, jeśli AI zawiedzie
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Wpadnij do {salon_name}!")

# --- 4. PARSOWANIE PLIKÓW (VCF) ---
def parse_vcf(file_content):
    """Przetwarza plik .vcf (wizytówki) na tabelę danych"""
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")
        
    contacts = []
    current = {}
    
    for line in content.splitlines():
        if line.startswith("BEGIN:VCARD"): 
            current = {}
        elif line.startswith("FN:") or line.startswith("N:"):
            if "Imię" not in current:
                parts = line.split(":", 1)[1]
                current["Imię"] = parts.replace(";", " ").strip()
        elif line.startswith("TEL"):
            if "Telefon" not in current:
                num = line.split(":", 1)[1]
                # Zostawiamy tylko cyfry
                clean = ''.join(filter(str.isdigit, num))
                # Dodajemy polski kierunkowy jeśli brakuje
                if len(clean) == 9: clean = "48" + clean
                current["Telefon"] = clean
        elif line.startswith("END:VCARD"):
            if "Imię" in current and "Telefon" in current:
                current["Ostatni Zabieg"] = "Import z pliku" # Domyślna wartość
                contacts.append(current)
                
    return pd.DataFrame(contacts)

