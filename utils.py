import google.generativeai as genai
import pandas as pd
import random
import streamlit as st

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            
            # ZMIANA NA MODEL STANDARDOWY (STABILNY)
            # gemini-pro jest darmowy w ramach limitów i bardzo szybki
            model_name = 'gemini-pro'
            
            config = genai.types.GenerationConfig(
                temperature=0.8,  # Trochę kreatywności, ale bez szaleństw
                candidate_count=1,
                max_output_tokens=100 # <--- OPTYMALIZACJA: Limitujemy długość, żeby AI kończyło szybciej (taniej i szybciej)
            )
            return genai.GenerativeModel(model_name, generation_config=config)
        else:
            return None
    except Exception as e:
        print(f"Błąd inicjalizacji AI: {e}")
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
    # Zabezpieczenie: ucinamy, jeśli AI się rozpędziło
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

# --- GENEROWANIE WIADOMOŚCI ---
def generate_single_message_debug(salon_name, campaign_goal, client_name, last_treatment):
    """
    Zwraca: (wiadomość, prompt, błąd)
    """
    if not model:
        return None, None, "❌ Brak połączenia z AI. Sprawdź klucz API."

    # Krótkie style, żeby nie marnować tokenów na czytanie
    vibe_list = [
        "Energiczna koleżanka",
        "Ciepła i troskliwa",
        "Krótko i konkretnie",
        "Ekskluzywnie"
    ]
    current_vibe = random.choice(vibe_list)

    # Prompt zoptymalizowany pod szybkość (krótszy, konkretny)
    prompt = f"""
    Jesteś: {salon_name}. Piszesz SMS do: {client_name}.
    Cel: {campaign_goal}.
    Ostatni zabieg: {last_treatment}.
    Styl: {current_vibe}.
    
    Wymogi:
    1. Wołacz imienia.
    2. Max 160 znaków.
    3. Bez polskich znaków.
    4. Żadnego marketingu typu "zapraszamy".
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        res = model.generate_content(prompt, safety_settings=safety)
        if res and res.text:
            return process_message(res.text.strip()), prompt, None
        else:
            return None, prompt, "Pusta odpowiedź"
    except Exception as e:
        return None, prompt, str(e)
