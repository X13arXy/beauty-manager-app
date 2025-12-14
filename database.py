import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- INICJALIZACJA BAZY ---
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Błąd połączenia z bazą: {e}")
        st.stop()

supabase: Client = init_supabase()

# --- LOGOWANIE I REJESTRACJA ---
def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return response.user
    except Exception as e:
        st.error(f"Błąd logowania: {e}")
        return None

def register_user(email, password, salon_name):
    """Rejestruje użytkownika i od razu tworzy profil z nazwą salonu"""
    try:
        # 1. Tworzymy użytkownika w Auth
        response = supabase.auth.sign_up({"email": email, "password": password})
        user = response.user
        
        if user:
            # 2. Od razu tworzymy wpis w tabeli profiles
            # Dzięki temu nazwa salonu jest zapisana od startu
            data = {
                "id": user.id,
                "nazwa_salonu": salon_name
            }
            supabase.table("profiles").insert(data).execute()
            return user
        return None
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")
        return None
def logout_user():
    supabase.auth.sign_out()

# --- OPERACJE NA DANYCH (CRUD) ---

# To jest ta poprawiona funkcja, o którą prosiłeś:
def add_client(salon_id, imie, telefon, zabieg, data):
    # Czyścimy numer telefonu z myślników i spacji
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    
    # Tu jest Twój FIX na daty (None zamiast pustego stringa)
    data_val = str(data) if data and str(data).strip() != "" else None
    
    try:
        supabase.table("klientki").insert({
            "salon_id": salon_id, 
            "imie": str(imie), 
            "telefon": clean_tel,
            "ostatni_zabieg": str(zabieg), 
            "data_wizyty": data_val
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

def get_clients(salon_id):
    try:
        res = supabase.table("klientki").select("*").eq("salon_id", salon_id).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def delete_client(client_id, salon_id):
    try:
        supabase.table("klientki").delete().eq("id", client_id).eq("salon_id", salon_id).execute()
        return True
    except:
        return False
def reset_password_email(email):
    try:
        # To wyśle maila z linkiem do zmiany hasła (obsługiwane przez Supabase)
        supabase.auth.reset_password_for_email(email, {
            "redirect_to": "http://localhost:8501" # Tutaj w przyszłości dasz adres swojej apki w chmurze
        })
        return True, "Link wysłany! Sprawdź email."
    except Exception as e:
        return False, str(e)
# --- ZARZĄDZANIE PROFILEM ---

def get_salon_name(user_id):
    """Pobiera nazwę salonu dla zalogowanego użytkownika"""
    try:
        # Pobieramy wiersz z tabeli profiles gdzie id = user_id
        res = supabase.table("profiles").select("nazwa_salonu").eq("id", user_id).execute()
        
        # Jeśli coś znalazło, zwracamy nazwę
        if res.data and len(res.data) > 0:
            return res.data[0].get("nazwa_salonu", "")
        else:
            return ""
    except Exception as e:
        return ""

def update_salon_name(user_id, new_name):
    """Aktualizuje lub tworzy wpis z nazwą salonu"""
    try:
        # Używamy 'upsert' (update lub insert)
        data = {
            "id": user_id,
            "nazwa_salonu": new_name
        }
        supabase.table("profiles").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu profilu: {e}")
        return False
def update_clients_bulk(data_list):
    """
    Przyjmuje listę słowników (zmienioną tabelę) i aktualizuje Supabase.
    Wymaga, aby w danych było pole 'id' (klucz główny).
    """
    try:
        if not data_list:
            return True, "Brak danych do zapisu."
            
        # upsert w Supabase aktualizuje wiersze, jeśli pasuje ID, 
        # lub dodaje nowe, jeśli ID nie ma (lub jest nowe)
        supabase.table("klientki").upsert(data_list).execute()
        return True, "Zapisano pomyślnie!"
    except Exception as e:
        return False, str(e)
# Wklej to na końcu pliku database.py

def delete_clients_by_ids(id_list, salon_id):
    """Usuwa listę klientek po ich ID"""
    try:
        if not id_list:
            return True
        # Usuwamy tylko te ID, które należą do danego salonu (bezpieczeństwo)
        supabase.table("klientki").delete().in_("id", id_list).eq("salon_id", salon_id).execute()
        return True
    except Exception as e:
        print(f"Błąd usuwania: {e}")
        return False
