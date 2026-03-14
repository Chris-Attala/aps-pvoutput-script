import requests
import time
import hmac
import hashlib
import base64
import uuid
import os
from datetime import datetime

# === DEBUG : Vérifie que les variables d'environnement sont bien chargées ===
print("=== DEBUG ENV VARS ===")
print("APS_APP_ID      :", os.getenv('APS_APP_ID') or "MISSING")
print("APS_APP_SECRET  :", (os.getenv('APS_APP_SECRET') or "MISSING")[:6] + "..." if os.getenv('APS_APP_SECRET') else "MISSING")
print("PVO_API_KEY     :", (os.getenv('PVO_API_KEY') or "MISSING")[:6] + "..." if os.getenv('PVO_API_KEY') else "MISSING")
print("PVO_SYSTEM_ID   :", os.getenv('PVO_SYSTEM_ID') or "MISSING")
print("Python version  :", os.getenv('PYTHON_VERSION') or "N/A (not set by Railway)")
print("All env keys    :", list(os.environ.keys()))
print("=====================\n")

# Variables fixes (pas besoin d'env vars pour celles-ci)
SYSTEM_SID = 'D24C931099345673'
ECU_ID = '215000085900'

# Variables d'environnement (doivent être définies dans Railway)
APP_ID = os.getenv('APS_APP_ID')
APP_SECRET = os.getenv('APS_APP_SECRET')
PVO_API_KEY = os.getenv('PVO_API_KEY')
PVO_SYSTEM_ID = os.getenv('PVO_SYSTEM_ID')

# Vérification rapide avant de continuer
if not APP_ID or not APP_SECRET:
    print("ERREUR : APP_ID ou APP_SECRET manquant ! Arrêt.")
    exit(1)

BASE_URL = 'https://openapi.apsystems.com'

def generate_signature(method, path, timestamp, nonce):
    string_to_sign = f"{timestamp}/{nonce}/{APP_ID}/{path}/{method.upper()}/HmacSHA256"
    mac = hmac.new(APP_SECRET.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')

def get_headers(path, method='GET'):
    timestamp = str(int(time.time() * 1000))
    nonce = str(uuid.uuid4()).replace('-', '')
    sig = generate_signature(method, path, timestamp, nonce)
    return {
        'X-CA-AppId': APP_ID,
        'X-CA-Timestamp': timestamp,
        'X-CA-Nonce': nonce,
        'X-CA-Signature-Method': 'HmacSHA256',
        'X-CA-Signature': sig,
        'Content-Type': 'application/json'
    }

def get_today_energy():
    # Endpoint recommandé d'après doc OpenAPI v2
    path = f'/user/api/v2/systems/summary/{SYSTEM_SID}'
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"Appel API vers : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status code : {r.status_code}")
        r.raise_for_status()
        data = r.json()
        print("Réponse API complète :", data)
        
        if data.get('code') == 0:
            today_kwh = data['data'].get('today') or data['data'].get('energy_today') or data['data'].get('today_energy')
            if today_kwh is not None:
                print(f"Énergie today trouvée : {today_kwh} kWh")
                return float(today_kwh)
            else:
                print("Aucune clé 'today' ou équivalent dans data['data']")
        else:
            print("Erreur API APsystems :", data.get('msg', data))
    except Exception as e:
        print("Erreur requête API :", str(e))
    return None

def push_pvoutput(energy_kwh):
    if energy_kwh is None:
        print("Aucune énergie à envoyer → skip push")
        return
    energy_wh = int(float(energy_kwh) * 1000)  # kWh → Wh
    date_str = datetime.now().strftime('%Y%m%d')
    url = 'https://pvoutput.org/service/r2/addoutput.jsp'
    params = {
        'd': date_str,
        'c1': energy_wh,  # Energy Generation
        # 'v2': peak_power_w  # à ajouter plus tard si on récupère le peak
    }
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=params, headers=headers)
        print("Réponse PVOutput :", r.text.strip())
        if r.status_code == 200 and "OK" in r.text:
            print("Push PVOutput réussi !")
        else:
            print("Échec push PVOutput")
    except Exception as e:
        print("Erreur push PVOutput :", str(e))

if __name__ == '__main__':
    print("Démarrage script APsystems → PVOutput")
    energy = get_today_energy()
    push_pvoutput(energy)
    print("Fin exécution")
