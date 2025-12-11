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
    # 1. Losowanie stylu (to masz super, zostawiamy)
    vibe_list = [
        "STYL: Przyjaciółka, dużo energii, emoji ✨. Bez oficjalnego tonu!",
        "STYL: Troskliwa, ciepła, nacisk na relaks 🌿. Spokojny ton.",
        "STYL: Konkretna, krótka, z humorem 😎. Krótka piłka.",
        "STYL: Ekskluzywna, elegancka, spraw by poczuła się wyjątkowo 💎."
    ]
    current_vibe = random.choice(vibe_list)

    # 2. Ulepszony Prompt z przykładami odmiany
    prompt = f"""
    Jesteś managerką salonu "{salon_name}". Napisz SMS do klienta: "{client_name}".
    
    ZADANIE:
    Napisz wiadomość zachęcającą do: {campaign_goal}.
    Ostatni zabieg klienta: {last_treatment} (nawiąż do niego, jeśli pasuje).
    
    WYMAGANY STYL: {current_vibe}
    
    ZASADY KRYTYCZNE:
    1. ZAWSZE odmieniaj imię w wołaczu!
       - Kuba -> Cześć Kubo!
       - Anna -> Hej Aniu!
       - Piotr -> Dzień dobry Piotrze!
    2. Nie używaj słów: "zapraszamy", "oferta", "rabat", "klient". To brzmi jak spam.
    3. Długość: absolutne maximum 160 znaków.
    4. Bez polskich znaków (usuń ogonki na końcu, ale teraz pisz po polsku).
    
    Treść wiadomości:
    """

    safety = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]

    try:
        # Generowanie
        res = model.generate_content(prompt, safety_settings=safety)
        raw_text = res.text.strip()
        
        # Jeśli odpowiedź jest pusta, rzuć błąd żeby wejść do except
        if not raw_text:
            raise ValueError("Pusta odpowiedź od AI")
            
        return process_message(raw_text)

    except Exception as e:
        # Tutaj printujemy błąd w logach (widoczne w terminalu, nie na stronie dla klienta)
        print(f"❌ Błąd generowania dla {client_name}: {e}")
        # Awaryjna wiadomość, ale spróbujmy chociaż trochę odmienić
        return usun_ogonki(f"Czesc {client_name}! {campaign_goal}. Wpadnij do {salon_name}!")

