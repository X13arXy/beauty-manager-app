import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# Próba importu biblioteki SMS
try:
    from smsapi.client import SmsApiPlClient
except ImportError:
    pass

def init_ai():
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
            return genai.GenerativeModel('gemini-2.0-flash')
        else:
            return None
    except Exception as e:
        st.error(f"❌ Błąd Gemini: {e}")
        return None

model = init_ai()

def usun_ogonki(tekst):
    """Usuwa polskie znaki."""
    if not isinstance(tekst, str): return ""
    mapa = {'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'}
    for pl, latin in mapa.items():
        tekst = tekst.replace(pl, latin)
    return tekst

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
                current_contact["Ostatni Zabieg"] = "Brak"
                contacts.append(current_contact)
    return pd.DataFrame(contacts)

def generate_sms_content(salon_name, client_data, campaign_goal, generate_template=False):
    """Generuje treść SMS (Unikalną lub Szablon)"""
    
    imie = "{imie}" if generate_template else client_data.get('imie', 'Klientko')
    
    # FILTR ZABIEGÓW
    raw_zabieg = str(client_data.get('ostatni_zabieg', '')).strip()
    zakazane_slowa = ['importowany', 'brak', 'nieznany', 'nan', 'none', '']
    
    if raw_zabieg.lower() in zakazane_slowa:
        instrukcja_zabieg = "Nie wspominaj o ostatnim zabiegu, bo nie wiemy co to było. Skup się tylko na celu wiadomości."
    else:
        instrukcja_zabieg = f"Możesz (ale nie musisz) luźno nawiązać do ostatniego zabiegu: {raw_zabieg}."

    if not model: 
        return usun_ogonki(f"Hej {imie}, zapraszamy do {salon_name}!")
    
    if generate_template:
        instr = f"Użyj znacznika {{imie}} w treści."
    else:
        instr = f"Napisz bezpośrednio do klientki {imie}. {instrukcja_zabieg}"

    # --- TUTAJ DODAŁEM ZAKAZ EMOJI ---
    prompt = f"""
    Jesteś recepcjonistką w salonie: {salon_name}.
    Napisz SMS. Cel: {campaign_goal}.
    
    WYTYCZNE:
    1. {instr}
    2. Styl: krótki, konkretny, miły.
    3. BEZWZGLĘDNY ZAKAZ UŻYWANIA EMOJI I IKON (To jest SMS GSM).
    4. Bez polskich znaków (usuń ogonki).
    5. Podpisz się: {salon_name}.
    6. Max 150 znaków.
    """
    
    try:
        res = model.generate_content(prompt)
        text = res.text.strip()
        if generate_template and "{imie}" not in text: text = f"Hej {{imie}}, {text}"
        
        # DODATKOWE CZYSZCZENIE (dla pewności usuwamy najczęstsze emotki ręcznie, gdyby AI zwariowało)
        # To prosty filtr, który usuwa znaki spoza standardowego ASCII
        text_clean = text.encode('ascii', 'ignore').decode('ascii')
        
        return usun_ogonki(text_clean) # Zwracamy wyczyszczony tekst
    except Exception as e:
        return f"BLAD AI: {str(e)}"

def send_sms_via_api(phone, message):
    token = st.secrets.get("SMSAPI_TOKEN", "")
    if not token: return False, "Brak Tokenu"
    try:
        client = SmsApiPlClient(access_token=token)
        client.sms.send(to=str(phone), message=message, from_="Eco") 
        return True, "OK"
    except Exception as e:
        return False, str(e)

def send_campaign_logic(target_df, template_content, campaign_goal, is_test, progress_bar, salon_name, unique_mode=False):
    total = len(target_df)
    status_box = st.empty()
    raport_lista = []
    
    for i, (index, row) in enumerate(target_df.iterrows()):
        imie_klientki = row.get('imie', 'Klientko')
        
        telefon = row.get('full_phone')
        if not telefon:
             kier = row.get('kierunkowy', '48')
             tel_base = row.get('telefon', '')
             telefon = str(kier) + str(tel_base)
        
        if unique_mode:
            final_msg = generate_sms_content(salon_name, row, campaign_goal, generate_template=False)
            time.sleep(0.5)
        else:
            try:
                final_msg = template_content.replace("{imie}", str(imie_klientki))
            except:
                final_msg = template_content

        if is_test:
            status_text = "🧪 Symulacja"
            status_box.info(f"[{i+1}/{total}] {imie_klientki}: {final_msg}")
            if not unique_mode: time.sleep(0.05) 
        else:
            success, info = send_sms_via_api(telefon, final_msg)
            status_text = "✅ Wysłano" if success else f"❌ Błąd: {info}"
            status_box.text(f"[{i+1}/{total}] Przetwarzanie: {imie_klientki}...")
        
        raport_lista.append({
            "Imię": imie_klientki,
            "Telefon": telefon,
            "Treść SMS": final_msg,
            "Status": status_text
        })

        if total > 0: progress_bar.progress(min((i + 1) / total, 1.0))

    status_box.success("🎉 Kampania zakończona!")
    return pd.DataFrame(raport_lista)
