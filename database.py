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
    """
    Rejestruje użytkownika i przekazuje nazwę salonu w metadanych.
    Resztę (tworzenie wpisu w tabeli profiles) załatwia Trigger SQL.
    """
    try:
        # Przekazujemy nazwę salonu w 'data', żeby SQL mógł ją przechwycić
        response = supabase.auth.sign_up({
            "email": email, 
            "password": password,
            "options": {
                "data": { "full_name": salon_name, "nazwa_salonu": salon_name }
            }
        })
        return response.user
    except Exception as e:
        st.error(f"Błąd rejestracji: {e}")
        return None

def logout_user():
    supabase.auth.sign_out()

def reset_password_email(email):
    try:
        # Pamiętaj, żeby w panelu Supabase -> Authentication -> URL Configuration
        # ustawić Site URL na swój adres (np. http://localhost:8501 lub adres chmury)
        supabase.auth.reset_password_for_email(email, {
            "redirect_to": "http://localhost:8501" 
        })
        return True, "Link wysłany! Sprawdź email."
    except Exception as e:
        return False, str(e)

# --- ZARZĄDZANIE PROFILEM ---

def get_salon_name(user_id):
    """Pobiera nazwę salonu dla zalogowanego użytkownika"""
    try:
        res = supabase.table("profiles").select("nazwa_salonu").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0].get("nazwa_salonu", "")
        return ""
    except Exception:
        return ""

def update_salon_name(user_id, new_name):
    try:
        data = {"id": user_id, "nazwa_salonu": new_name}
        supabase.table("profiles").upsert(data).execute()
        return True
    except Exception as e:
        st.error(f"Błąd zapisu profilu: {e}")
        return False

# --- KLIENCI (CRUD) ---

def add_client(salon_id, imie, telefon, zabieg, data, kierunkowy="48"):
    # Czyścimy dane przed wysłaniem
    clean_tel = ''.join(filter(str.isdigit, str(telefon)))
    clean_kier = ''.join(filter(str.isdigit, str(kierunkowy)))
    
    # Fix na daty (puste stringi na None)
    data_val = str(data) if data and str(data).strip() != "" else None
    
    try:
        supabase.table("klientki").insert({
            "salon_id": salon_id, 
            "imie": str(imie), 
            "telefon": clean_tel,
            "kierunkowy": clean_kier, 
            "ostatni_zabieg": str(zabieg), 
            "data_wizyty": data_val
        }).execute()
        return True, ""
    except Exception as e:
        return False, str(e)

def get_clients(salon_id):
    try:
        # Mimo włączonego RLS w bazie, filtrujemy też tutaj dla porządku
        res = supabase.table("klientki").select("*").eq("salon_id", salon_id).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

def update_clients_bulk(data_list):
    """Masowa aktualizacja lub dodawanie (Upsert)"""
    try:
        if not data_list: return True, "Brak danych."
        supabase.table("klientki").upsert(data_list).execute()
        return True, "Zapisano pomyślnie!"
    except Exception as e:
        return False, str(e)

def delete_clients_by_ids(id_list, salon_id):
    """Usuwa listę klientek (bezpiecznie sprawdzając salon_id)"""
    try:
        if not id_list: return True
        # Usuwamy tylko jeśli ID jest na liście I należy do tego salonu
        supabase.table("klientki").delete().in_("id", id_list).eq("salon_id", salon_id).execute()
        return True
    except Exception as e:
        print(f"Błąd usuwania: {e}")
        return False
