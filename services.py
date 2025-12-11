import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# Import biblioteki SMSAPI (opcjonalny, z obsługą błędu)
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# --- AI GEMINI ---
def init_ai():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        return genai.GenerativeModel('models/gemini-flash-latest')
    except Exception as e:
        st.error(f"❌ Błąd konfiguracji Gemini: {e}")
        return None

model = init_ai()

def generate_sms_content(salon_name, client_name, goal):
    if not model: return None
    
    prompt = f"""
    Jesteś recepcjonistką w salonie: {salon_name}.
    Napisz SMS do klientki {client_name}.
    Cel: {goal}.
    INSTRUKCJE:
    Zacznij od imienia. Styl: Ciepły, miły. Użyj języka korzyści.
    Podpisz się nazwą salonu. Pisz poprawną polszczyzną.
    LIMIT ZNAKÓW TO 160.
    """
    try:
        res = model.generate_content(prompt)
        return usun_ogonki(res.text.strip()) if res.text else None
    except Exception as e:
        st.error(f"Błąd AI: {e}")
        return None

# --- NARZĘDZIA ---
def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

# --- PARSOWANIE VCF ---
def parse_vcf(file_content):
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")
        
    contacts = []
    current_contact = {}
    
    for line in content.splitlines():
        if line.startswith("BEGIN:VCARD"):
            current_contact = {}
        elif line.startswith("FN:") or line.startswith("N:"): 
            if "Imię" not in current_contact:
                parts = line.split(":", 1)[1]
                current_contact["Imię"] = parts.replace(";", " ").strip()
        elif line.startswith("TEL"): 
            if "Telefon" not in current_contact: 
                number = line.split(":", 1)[1]
                clean_number = ''.join(filter(str.isdigit, number))
                if len(clean_number) > 9 and clean_number.startswith("48"): pass 
                elif len(clean_number) == 9: clean_number = "48" + clean_number 
                current_contact["Telefon"] = clean_number
        elif line.startswith("END:VCARD"):
            if "Imię" in current_contact and "Telefon" in current_contact:
                current_contact["Ostatni Zabieg"] = "Nieznany"
                contacts.append(current_contact)
    
    return pd.DataFrame(contacts)

# --- WYSYŁKA SMS (LOGIKA) ---
def send_campaign_logic(target_df, generated_text, is_test_mode, progress_bar, preview_name):
    sms_token = st.secrets.get("SMSAPI_TOKEN", "")
    client = None

    if not is_test_mode:
        if not sms_token:
            st.error("❌ Brak tokenu SMSAPI!")
            return
        try:
            client = SmsApiPlClient(access_token=sms_token)
        except Exception as e:
            st.error(f"Błąd logowania SMSAPI: {e}")
            return

    total = len(target_df)
    
    for index, row in target_df.iterrows():
        # Personalizacja
        final_text = generated_text
        if preview_name and preview_name in generated_text:
            final_text = generated_text.replace(preview_name, row['imie'])
        
        clean_text = usun_ogonki(final_text)

        if is_test_mode:
            print(f"[TEST] Do: {row['telefon']} | {clean_text}")
        else:
            try:
                client.sms.send(to=row['telefon'], message=clean_text)
            except Exception as e:
                st.error(f"Błąd wysyłki do {row['imie']}: {e}")

        time.sleep(1) # Ważne opóźnienie
        
        # Aktualizacja paska postępu
        prog = min((index + 1) / total, 1.0)
        progress_bar.progress(prog)
