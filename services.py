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
            # Używamy wersji stabilnej
            return genai.GenerativeModel('gemini-2.0-flash')
        else:
            return None
    except Exception as e:
        st.error(f"❌ Błąd Gemini: {e}")
        return None

model = init_ai()

# --- FUNKCJE POMOCNICZE ---
def usun_ogonki(tekst):
    if not isinstance(tekst, str):
        return ""
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
        # Obsługa różnych wielkości liter w kluczach
        imie = client_data.get('imie', client_data.get('Imię', 'Klientko'))
        ostatni_zabieg = client_data.get('ostatni_zabieg', client_data.get('Ostatni Zabieg', 'nieznany'))

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
    5. Bez emoji. 
    """
    
    try:
        res = model.generate_content(prompt)
        text = res.text.strip()
        return usun_ogonki(text)
    except Exception as e:
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

def send_campaign_logic(target_df, campaign_goal, template_content, is_test, progress_bar, preview_client_name, salon_name):
    """
    Logika pętli wysyłkowej z RAPORTOWANIEM.
    Zwraca DataFrame z podsumowaniem wysyłki.
    """
    total = len(target_df)
    status_box = st.empty()
    
    # Lista, do której będziemy zbierać wyniki
    raport_lista = []
    
    for i, (index, row) in enumerate(target_df.iterrows()):
        imie = row.get('imie', row.get('Imię', 'Klientko'))
        telefon = row.get('telefon', row.get('Telefon'))
        
        # 1. Generowanie (AI)
        final_msg = generate_sms_content(salon_name, row, campaign_goal)
        time.sleep(1.0) 

        # 2. Wysyłka / Symulacja
        if is_test:
            status_text = "🧪 Test (Symulacja)"
            status_box.info(f"[{i+1}/{total}] Generuję dla: {imie}...\nAI: {final_msg}")
        else:
            success, info = send_sms_via_api(telefon, final_msg)
            status_text = "✅ Wysłano" if success else f"❌ Błąd: {info}"
            status_box.text(f"[{i+1}/{total}] Wysłano do: {imie}")
            time.sleep(0.2)

        # 3. Dodajemy do raportu
        raport_lista.append({
            "Imię": imie,
            "Telefon": telefon,
            "Treść SMS": final_msg,
            "Status": status_text
        })

        # Pasek postępu
        current_progress = (i + 1) / total
        if current_progress > 1.0: current_progress = 1.0
        progress_bar.progress(current_progress)

    status_box.success("Kampania zakończona!")
    
    # Zwracamy tabelę z wynikami
    return pd.DataFrame(raport_lista)
