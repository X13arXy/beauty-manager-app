import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import random

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Używamy modelu Flash (jest szybki i wystarczająco kreatywny)
        return genai.GenerativeModel('models/gemini-1.5-flash')
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None

model = init_ai()

# --- NARZĘDZIA TECHNICZNE ---
def usun_ogonki(tekst):
    """Zamienia polskie znaki na łacińskie (dla tanich SMS)"""
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
    """Generuje UNIKALNĄ, ciepłą wiadomość dla konkretnej osoby"""
    
    # Lista różnych stylów, żeby AI nie pisało w kółko tego samego
    style = [
        "Bardzo entuzjastyczny i radosny",
        "Ciepły, spokojny i troskliwy",
        "Krótki, konkretny, ale z uśmiechem",
        "Pytający o samopoczucie i zapraszający"
    ]
    wylosowany_styl = random.choice(style)

    # PROMPT PREMIUM (Relacyjny)
    prompt = f"""
    Jesteś managerką relacji w salonie "{salon_name}". 
    Twoim celem jest dbanie o klientki, nie tylko sprzedaż.
    
    Napisz SMS do klientki: {client_name}.
    Ostatnio była na: {last_treatment}.
    
    CEL WIADOMOŚCI: {campaign_goal}.
    
    TWOJE INSTRUKCJE (BARDZO WAŻNE):
    1. Styl: {wylosowany_styl}.
    2. Pisz jak człowiek do człowieka (koleżanka do koleżanki). Unikaj korporacyjnego języka.
    3. Zacznij od imienia w wołaczu (np. "Cześć Kasiu!", "Dzień dobry Aniu").
    4. Jeśli to pasuje do celu, nawiąż delikatnie do ostatniego zabiegu ({last_treatment}), np. "jak tam Twoje rzęsy?".
    5. Dodaj 1 lub 2 emoji pasujące do treści (np. 💅, 🌸, ✨, ☕).
    6. Podpisz się nazwą salonu.
    7. Pisz normalnie po polsku (z ą, ę) - system sam usunie ogonki.
    8. Całość musi mieć MAX 150 znaków.
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Retry logic (3 próby)
        for _ in range(3):
            try:
                res = model.generate_content(prompt, safety_settings=safety)
                raw_text = res.text.strip()
                # Czyścimy technicznie
                return process_message(raw_text)
            except:
                time.sleep(1)
        
        # Fallback (Gdyby AI padło)
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Pozdrawiamy, {salon_name}") 
    except:
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Pozdrawiamy, {salon_name}")

# --- IMPORT Z TELEFONU (BEZ ZMIAN) ---
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

