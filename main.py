import requests
import time
import hmac
import hashlib
import base64
import uuid
import os
from datetime import datetime

# DEBUG ENV VARS
print("=== DEBUG ENV VARS ===")
print("APS_APP_ID      :", os.getenv('APS_APP_ID') or "MISSING")
print("APS_APP_SECRET  :", (os.getenv('APS_APP_SECRET') or "MISSING")[:6] + "..." if os.getenv('APS_APP_SECRET') else "MISSING")
print("PVO_API_KEY     :", (os.getenv('PVO_API_KEY') or "MISSING")[:6] + "..." if os.getenv('PVO_API_KEY') else "MISSING")
print("PVO_SYSTEM_ID   :", os.getenv('PVO_SYSTEM_ID') or "MISSING")
print("All env keys    :", list(os.environ.keys()))
print("=====================\n")

# Fixes
SYSTEM_SID = 'D24C931099345673'
ECU_ID = '215000085900'

APP_ID = os.getenv('APS_APP_ID')
APP_SECRET = os.getenv('APS_APP_SECRET')
PVO_API_KEY = os.getenv('PVO_API_KEY')
PVO_SYSTEM_ID = os.getenv('PVO_SYSTEM_ID')

if not APP_ID or not APP_SECRET:
    print("ERREUR : APP_ID ou APP_SECRET manquant ! Arrêt.")
    exit(1)

BASE_URL = 'https://api.apsystemsema.com:9282'

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

def test_endpoint(path):
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"Test endpoint : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status code : {r.status_code}")
        data = r.json()
        print("Réponse complète :", data)
        if data.get('code') == 0:
            print("Succès ! Data :", data.get('data'))
            return data
        else:
            print("Erreur :", data.get('msg') or data.get('message') or data)
    except Exception as e:
        print("Erreur requête :", str(e))
    return None

def get_today_energy():
    # Test ECU summary (manuel : /user/api/v2/systems/{sid}/devices/ecu/summary/{eid})
    path_ecu_summary = f'/user/api/v2/systems/{SYSTEM_SID}/devices/ecu/summary/{ECU_ID}'
    url = BASE_URL + path_ecu_summary
    headers = get_headers(path_ecu_summary)
    try:
        print(f"Test ECU summary : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status code ECU summary : {r.status_code}")
        data = r.json()
        print("Réponse ECU summary :", data)
        if data.get('code') == 0:
            today_kwh = data['data'].get('today') or data['data'].get('energy_today')
            if today_kwh is not None:
                print(f"Énergie today trouvée : {today_kwh} kWh")
                return float(today_kwh)
        else:
            print("Erreur ECU summary :", data.get('msg') or data)
    except Exception as e:
        print("Erreur requête ECU summary :", str(e))

    # Fallback au summary système si ECU fail
    path_summary = f'/user/api/v2/systems/summary/{SYSTEM_SID}'
    # ... même code que avant
    # (copie le bloc try du summary original ici si besoin)

    return None

def push_pvoutput(energy_kwh):
    if energy_kwh is None:
        print("Aucune énergie → skip push")
        return
    energy_wh = int(float(energy_kwh) * 1000)
    date_str = datetime.now().strftime('%Y%m%d')
    url = 'https://pvoutput.org/service/r2/addoutput.jsp'
    params = {'d': date_str, 'c1': energy_wh}
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=params, headers=headers)
        print("PVOutput réponse :", r.text.strip())
        if "OK" in r.text.upper():
            print("Push réussi !")
        else:
            print("Échec push")
    except Exception as e:
        print("Erreur push :", str(e))

if __name__ == '__main__':
    print("Démarrage")
    energy = get_today_energy()
    push_pvoutput(energy)
    print("Fin")
