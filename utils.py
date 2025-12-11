import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import random

# --- KONFIGURACJA AI (PODKRĘCONA KREATYWNOŚĆ) ---
def init_ai():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # USTAWIAMY TEMPERATURĘ NA 0.9 (Bardzo wysoka kreatywność)
        # Dzięki temu AI będzie rzadziej powtarzać te same zwroty
        config = genai.types.GenerationConfig(
            temperature=0.9,
            top_p=0.95,
            candidate_count=1
        )
        return genai.GenerativeModel('models/gemini-1.5-flash', generation_config=config)
    except Exception as e:
        st.error(f"Błąd konfiguracji AI: {e}")
        return None

model = init_ai()

# --- NARZĘDZIA TECHNICZNE ---
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

def generate_single_message(salon_name, campaign_goal, client_name, last_treatment):
    """Generuje wiadomość z DUŻĄ energią i różnorodnością"""
    
    # --- LOSOWANIE OSOBOWOŚCI (To jest klucz do różnorodności) ---
    vibe_list = [
        "ZWARIOWANA PRZYJACIÓŁKA: Dużo energii, wykrzykniki, emocje! Pisz tak, jakbyś nie widziała jej sto lat.",
        "TROSKLIWA OPIEKUNKA: Skup się na relaksie, odpoczynku, 'chwili dla siebie'. Ciepło i spokój.",
        "EKSPERTKA BEAUTY: Skup się na efekcie 'wow', blasku, byciu gwiazdą. Komplementuj.",
        "KRÓTKO I NA TEMAT (ALE MIŁO): Konkret, ale z uśmiechem. Bez zbędnego lania wody.",
        "TAJEMNICZA: Zacznij od pytania, zrób aurę ekskluzywności."
    ]
    # Losujemy jeden styl dla tej konkretnej klientki
    current_vibe = random.choice(vibe_list)

    # --- PROMPT "BESTIE" ---
    prompt = f"""
    Jesteś właścicielką salonu "{salon_name}". Piszesz prywatnego SMS-a do klientki: {client_name}.
    Ostatnio robiła: {last_treatment}.
    
    CEL: {campaign_goal}.
    
    TWOJA ROLA W TYM SMSIE: {current_vibe} (Trzymaj się tego stylu!).
    
    BARDZO WAŻNE ZASADY (PRZESTRZEGAJ ICH):
    1. ZABRONIONE: Nie używaj słów "zapraszamy", "skorzystaj", "oferujemy", "usługi". To brzmi jak bot!
    2. ZAMIAST TEGO: Pisz "wpadaj", "mam dla Ciebie", "zróbmy coś fajnego", "tęsknimy".
    3. Zacznij od imienia w WOŁACZU (np. "Hejka Aniu!", "Cześć Kasiu!").
    4. Dodaj 2-3 emoji pasujące do wylosowanego stylu.
    5. Jeśli to pasuje, nawiąż luźno do ostatniego zabiegu (np. "jak tam pazurki?", "czas na relaks?").
    6. Podpisz się tylko nazwą salonu.
    7. Pisz poprawną polszczyzną (bez 'ogonków' zajmiemy się później).
    8. Max 160 znaków.
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Próbujemy 3 razy
        for attempt in range(3):
            try:
                res = model.generate_content(prompt, safety_settings=safety)
                raw_text = res.text.strip()
                return process_message(raw_text)
            except:
                time.sleep(1) # Krótka przerwa
        
        # Fallback
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Czekamy na Ciebie w {salon_name}!") 
    except:
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Czekamy na Ciebie w {salon_name}!")

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
