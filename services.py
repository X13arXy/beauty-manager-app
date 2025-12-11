import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# Próba importu biblioteki SMS
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

# --- KONFIGURACJA AI ---
def init_ai():
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            # ZMIANA: Używamy wersji stabilnej (większe limity)
            return genai.GenerativeModel('models/gemini-2.5-flash')
        else:
            return None
    except Exception as e:
        st.error(f"❌ Błąd Gemini: {e}")
        return None

model = init_ai()

# --- FUNKCJE POMOCNICZE ---
def usun_ogonki(tekst):
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

def parse_vcf(file_content):
    """Import kontaktów z pliku VCF"""
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

# --- LOGIKA GENEROWANIA I WYSYŁKI ---

def generate_sms_content(salon_name, client_data, campaign_goal):
    """
    Generuje treść SMS. 
    Obsługuje zarówno 'row' (wiersz z DataFrame) jak i 'string' (samo imię dla podglądu).
    """
    
    # 1. Rozpoznaj, czy client_data to wiersz czy imię
    if isinstance(client_data, str):
        imie = client_data
        ostatni_zabieg = "nieznany"
    else:
        imie = client_data.get('imie', 'Klientko')
        ostatni_zabieg = client_data.get('ostatni_zabieg', 'nieznany')

    if not model: 
        return usun_ogonki(f"Hej {imie}, zapraszamy do {salon_name}!")
    
    prompt = f"""
    Jesteś recepcjonistką w salonie: {salon_name}.
    Napisz SMS do klientki: {imie}.
    Ostatni zabieg: {ostatni_zabieg}.
    Cel: {campaign_goal}.
    WYTYCZNE:
    1. Krótko, miło, styl relacyjny.
    2. Bez polskich znaków (usuń ogonki).
    3. Podpisz się: {salon_name}.
    4. Max 150 znaków.
    """
    
    try:
        res = model.generate_content(prompt)
        text = res.text.strip()
        return usun_ogonki(text)
    except Exception as e:
        # ZMIANA: Zwracamy treść błędu, żebyś wiedział co się dzieje
        return f"BLAD AI: {str(e)}"

def send_sms_via_api(phone, message):
    """Wysyła SMS przez bramkę SMSAPI"""
    token = st.secrets.get("SMSAPI_TOKEN", "")
    if not token: return False, "Brak tokenu"
    
    try:
        client = SmsApiPlClient(access_token=token)
        client.sms.send(to=str(phone), message=message)
        return True, "OK"
    except Exception as e:
        return False, str(e)
