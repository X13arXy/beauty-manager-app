import google.generativeai as genai
import pandas as pd
import random
import streamlit as st

# --- 1. KONFIGURACJA AI (Z ZABEZPIECZENIEM) ---
def init_ai():
    # Sprawdzamy czy w ogóle jest klucz
    if "GOOGLE_API_KEY" not in st.secrets:
        return None

    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        # Próbujemy zainicjować model Flash (jest najnowszy i darmowy)
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception:
        # Jeśli cokolwiek pójdzie nie tak, zwracamy None (co uruchomi tryb symulacji)
        return None

model = init_ai()

# --- 2. NARZĘDZIA ---
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

# --- 3. GENEROWANIE WIADOMOŚCI (HYBRYDOWE) ---
def generate_single_message_debug(salon_name, campaign_goal, client_name, last_treatment):
    
    # --- OPCJA A: PRAWDZIWE AI (JEŚLI DZIAŁA) ---
    if model:
        vibe_list = ["Energiczna kolezanka", "Ciepła i troskliwa", "Konkretna"]
        current_vibe = random.choice(vibe_list)

        prompt = f"""
        Jesteś: {salon_name}. SMS do: {client_name}.
        Cel: {campaign_goal}. Zabieg: {last_treatment}.
        Styl: {current_vibe}.
        1. Wołacz imienia (np. Aniu).
        2. Max 160 znaków.
        3. Bez ogonków.
        """
        safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]
        
        try:
            res = model.generate_content(prompt, safety_settings=safety)
            if res.text:
                return process_message(res.text.strip()), prompt, None
        except Exception as e:
            # Jeśli AI rzuci błędem (404, 429), nie panikujemy -> idziemy do Opcji B
            print(f"Awaria AI: {e}")
            pass 

    # --- OPCJA B: SYMULACJA AI (DARMOWA I NIEZAWODNA) ---
    # To się uruchomi, jeśli klucz nie działa lub Google rzuci błędem
    
    # Prosta "sztuczna inteligencja" na piechotę ;)
    szablony = [
        f"Czesc {client_name}! {campaign_goal}. Wpadnij na chwile relaksu do {salon_name}!",
        f"Hejka {client_name}! Dawno Cie nie bylo. {campaign_goal} czeka w {salon_name}.",
        f"Dzien dobry {client_name}. Mamy cos specjalnego: {campaign_goal}. Zapraszamy, {salon_name}.",
        f"{client_name}, tesknimy! Wpadnij odswiezyc look po {last_treatment}. {campaign_goal}!",
        f"Hej {client_name}! {campaign_goal} tylko dla naszych klientek. Do zobaczenia w {salon_name}."
    ]
    
    fake_msg = random.choice(szablony)
    return usun_ogonki(fake_msg), "SYMULACJA (Brak połączenia z AI)", "⚠️ Działam w trybie OFFLINE (AI niedostępne)"
