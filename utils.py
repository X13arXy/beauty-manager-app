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

# --- NARZĘDZIA TEKSTOWE ---
def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def generate_single_message(salon_name, campaign_goal, client_name, last_treatment):
    """Generuje JEDNĄ wiadomość (do podglądu lub wysyłki)"""
    prompt = f"""
    Jesteś recepcjonistką w salonie beauty "{salon_name}".
    Napisz SMS do klientki: {client_name}.
    Ostatni zabieg: {last_treatment}.
    Cel kampanii: {campaign_goal}.
    
    ZASADY:
    1. Zacznij od imienia w wołaczu (Cześć Kasiu).
    2. Styl: Miły, ciepły, krótki.
    3. Podpisz się: {salon_name}.
    4. Pisz poprawną polszczyzną (my usuniemy ogonki).
    5. Max 160 znaków.
    """
    try:
        # Próbujemy 3 razy w razie błędu API
        for _ in range(3):
            try:
                res = model.generate_content(prompt)
                return usun_ogonki(res.text.strip())
            except:
                time.sleep(1)
        return f"Czesc {client_name}! Zapraszamy do {salon_name}." # Tekst awaryjny
    except:
        return f"Czesc {client_name}! Zapraszamy do {salon_name}."

# --- IMPORT Z TELEFONU ---
def parse_vcf(file_content):
    """Czyta pliki kontaktów .vcf z telefonu"""
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