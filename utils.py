import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import random

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Ustawiamy wyższą "temperaturę" (0.85), żeby AI było bardziej kreatywne i mniej "robotyczne"
        config = genai.types.GenerationConfig(
            temperature=0.85,
            candidate_count=1
        )
        return genai.GenerativeModel('models/gemini-1.5-flash', generation_config=config)
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

def generate_single_message(salon_name, campaign_goal, client_name, last_treatment):
    """Generuje UNIKALNĄ, ciepłą wiadomość."""
    
    # 1. Losujemy "Vibe" wiadomości, żeby każda była inna
    vibe_list = [
        "Entuzjastyczna i pełna energii (użyj wykrzyknika i ognia)",
        "Ciepła, troskliwa i spokojna (jak dobra przyjaciółka)",
        "Tajemnicza i intrygująca (zadaj pytanie)",
        "Krótka, konkretna, ale bardzo miła"
    ]
    current_vibe = random.choice(vibe_list)

    # 2. Prompt nastawiony na relację
    prompt = f"""
    Jesteś właścicielką salonu "{salon_name}". Piszesz prywatnego SMS-a do swojej stałej klientki.
    
    KLIENTKA: {client_name}
    BYŁA OSTATNIO NA: {last_treatment}
    CEL WIADOMOŚCI: {campaign_goal}
    
    TWÓJ STYL W TEJ WIADOMOŚCI: {current_vibe}.
    
    ZASADY (BEZWZGLĘDNE):
    1. Zacznij od imienia w WOŁACZU (np. "Hej Aniu!", "Cześć Kasiu").
    2. Pisz LUŹNO. Unikaj słów typu "zapraszamy do skorzystania", "oferujemy". Zamiast tego pisz: "wpadnij", "mamy coś ekstra".
    3. Jeśli to pasuje, nawiąż do ostatniego zabiegu (np. "jak się trzymają paznokcie?").
    4. Dodaj 1-2 emoji pasujące do stylu.
    5. Podpisz się tylko nazwą salonu.
    6. Pisz poprawną polszczyzną (ogonki usuniemy sami).
    7. Max 160 znaków.
    """
    
    # Wyłączenie filtrów bezpieczeństwa
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Próbujemy 3 razy (Retry Logic)
        for attempt in range(3):
            try:
                res = model.generate_content(prompt, safety_settings=safety)
                raw_text = res.text.strip()
                # Czyścimy technicznie
                return usun_ogonki(raw_text)
            except Exception as e:
                # Jeśli błąd limitów (429), czekamy dłużej
                time.sleep(2 + attempt) 
        
        # Fallback (Gdyby AI padło 3 razy)
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Sciskamy, {salon_name}") 
    except:
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Sciskamy, {salon_name}")

# --- IMPORT (BEZ ZMIAN) ---
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
