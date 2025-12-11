import google.generativeai as genai
import os

# Konfiguracja API - wpisz klucz tutaj lub upewnij się, że masz go w zmiennych środowiskowych
# genai.configure(api_key="TU_WKLEJ_SWOJ_KLUCZ_JESLI_NIE_MASZ_W_ENV")

print(f"{'NAZWA DO WPISANIA W KODZIE':<35} | {'WIDOCZNA NAZWA'}")
print("="*70)

try:
    for m in genai.list_models():
        # Filtrujemy tylko modele, które potrafią generować treść (nie interesują nas modele do embeddingów)
        if 'generateContent' in m.supported_generation_methods:
            # Usuwamy prefix 'models/' dla czytelności, choć w kodzie można używać z nim lub bez
            clean_name = m.name.replace("models/", "")
            print(f"{clean_name:<35} | {m.displayName}")
except Exception as e:
    print(f"Wystąpił błąd: {e}")
