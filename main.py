import requests
import time
import hmac
import hashlib
import base64
import uuid
import os
from datetime import datetime

# DEBUG ENV
print("=== DEBUG ENV VARS ===")
print("APS_APP_ID      :", os.getenv('APS_APP_ID') or "MISSING")
print("APS_APP_SECRET  :", (os.getenv('APS_APP_SECRET') or "MISSING")[:6] + "..." if os.getenv('APS_APP_SECRET') else "MISSING")
print("PVO_API_KEY     :", (os.getenv('PVO_API_KEY') or "MISSING")[:6] + "..." if os.getenv('PVO_API_KEY') else "MISSING")
print("PVO_SYSTEM_ID   :", os.getenv('PVO_SYSTEM_ID') or "MISSING")
print("All env keys    :", list(os.environ.keys()))
print("=====================\n")

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

def test_endpoint(path, label=""):
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"{label} - Test : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"{label} - Status : {r.status_code}")
        if r.status_code != 200:
            print(f"{label} - Réponse non-JSON ou erreur : {r.text}")
            return None
        data = r.json()
        print(f"{label} - Réponse complète :", data)
        if data.get('code') == 0:
            print(f"{label} - Succès ! Data :", data.get('data'))
            return data
        else:
            print(f"{label} - Erreur :", data.get('msg') or data.get('message') or data)
    except Exception as e:
        print(f"{label} - Erreur requête :", str(e))
    return None

def get_realtime_power():
    path = f'/ecu/{ECU_ID}/realtime'
    data = test_endpoint(path, "Realtime ECU")
    if data and data.get('code') == 0:
        power = data['data'].get('power') or data['data'].get('current_power') or data['data'].get('power_now')
        if power is not None:
            print(f"Power actuelle trouvée : {power} W")
            return float(power)
    return None

def test_list():
    path = '/user/api/v2/ecu/list'  # ou '/user/api/v2/systems' si ça change
    data = test_endpoint(path, "Liste ECU/Systèmes")
    if data and data.get('code') == 0:
        print("Systèmes/ECU visibles :", data.get('data'))

def push_current_power(power_w):
    if power_w is None:
        print("Aucune puissance → skip push")
        return
    date_str = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H:%M')
    url = 'https://pvoutput.org/service/r2/addstatus.jsp'  # addstatus pour live data (pas addoutput)
    params = {
        'd': date_str,
        't': time_str,
        'v2': int(power_w),  # Peak Power (on utilise pour puissance actuelle)
        'c1': 0,             # Energy Generation = 0 (pas de daily)
        'm': 'Current power from EMA realtime (Lv0)'
    }
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=params, headers=headers)
        print("PVOutput addstatus réponse :", r.text.strip())
        if "OK" in r.text.upper():
            print("Push puissance actuelle réussi !")
        else:
            print("Échec push puissance")
    except Exception as e:
        print("Erreur push puissance :", str(e))

if __name__ == '__main__':
    print("Démarrage - Mode Lv0 limité")
    test_list()                # Voir si on voit au moins notre ECU
    power = get_realtime_power()  # Essayer de récupérer la puissance live
    push_current_power(power)
    print("Fin exécution")
