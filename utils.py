import google.generativeai as genai
import pandas as pd
import random
import streamlit as st

# --- 1. KONFIGURACJA AI (PĘTLA SZUKAJĄCA) ---
def init_ai():
    # 1. Sprawdź czy klucz istnieje
    if "GOOGLE_API_KEY" not in st.secrets:
        st.error("Brak klucza API w secrets.toml!")
        return None

    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)

    # 2. LISTA WSZYSTKICH MOŻLIWYCH NAZW (Od najnowszych)
    # Kod będzie próbował każdą po kolei, aż któraś zadziała.
    lista_modeli = [
        "gemini-1.5-flash",          # Standardowa nazwa
        "gemini-1.5-flash-latest",   # Wersja "Latest" o której wspominałeś
        "gemini-1.5-flash-001",      # Wersja numerowana
        "gemini-1.5-pro",            # Wersja Pro (mocniejsza)
        "gemini-pro",                # Klasyk (stary, ale jary)
        "models/gemini-1.5-flash"    # Czasem wymagany jest przedrostek
    ]

    for nazwa in lista_modeli:
        try:
            # Próba inicjalizacji
            model = genai.GenerativeModel(nazwa)
            
            # TEST POŁĄCZENIA (Ważne!)
            # Próbujemy wygenerować jedno słowo, żeby upewnić się, że to naprawdę działa
            # Jeśli tu wystąpi błąd, kod przeskoczy do 'except' i spróbuje następny model
            test_response = model.generate_content("Test", request_options={"timeout": 5})
            
            if test_response:
                print(f"✅ SUKCES! Połączono z modelem: {nazwa}")
                return model
                
        except Exception as e:
            # Jeśli ten model nie działa, logujemy to w konsoli i idziemy dalej
            print(f"⚠️ Model {nazwa} nie odpowiada: {e}")
            continue

    # Jeśli pętla się skończy i nic nie zadziałało:
    print("❌ Żaden model nie zadziałał.")
    return None

model = init_ai()

# --- 2. NARZĘDZIA POMOCNICZE ---
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
                current["Ostatni Zabieg"] = "Import"
                contacts.append(current)
    return pd.DataFrame(contacts)

# --- 3. FUNKCJA GENERUJĄCA ---
def generate_single_message_debug(salon_name, campaign_goal, client_name, last_treatment):
    
    # Jeśli model nie został znaleziony w pętli init_ai
    if not model:
        return None, "Brak połączonego modelu", "⚠️ Działam w trybie OFFLINE (Sprawdź logi, żaden z 6 modeli nie zadziałał)"

    # Style z Emotkami
    styles = [
        "Styl: Przyjaciółka, dużo energii! Użyj emotek ✨💖",
        "Styl: Relaks i Zen. Emotki roślinne 🌿🌸",
        "Styl: Konkretnie, krótko i z uśmiechem 😎",
        "Styl: Ekskluzywnie i elegancko 💎"
    ]
    current_style = random.choice(styles)

    prompt = f"""
    Jesteś: {salon_name}. SMS do: {client_name}.
    Cel: {campaign_goal}. Zabieg: {last_treatment}.
    WYMÓG STYLU: {current_style}
    
    ZASADY:
    1. Użyj wołacza (np. Aniu).
    2. Max 160 znaków.
    3. Bez polskich znaków, ale ZOSTAW EMOTKI.
    """
    
    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Próba generowania
        res = model.generate_content(prompt, safety_settings=safety)
        if res.text:
            return process_message(res.text.strip()), prompt, None
        else:
            return None, prompt, "Model zwrócił pustą odpowiedź"

    except Exception as e:
        return None, prompt, f"Błąd w trakcie generowania: {e}"
