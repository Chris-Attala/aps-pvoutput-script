import requests
import time
import hmac
import hashlib
import base64
import uuid
import os
from datetime import datetime

print("=== DEBUG ENV VARS ===")
print("APS_APP_ID      :", os.getenv('APS_APP_ID') or "MISSING")
print("APS_APP_SECRET  :", (os.getenv('APS_APP_SECRET') or "MISSING")[:6] + "..." if os.getenv('APS_APP_SECRET') else "MISSING")
print("PVO_API_KEY     :", (os.getenv('PVO_API_KEY') or "MISSING")[:6] + "..." if os.getenv('PVO_API_KEY') else "MISSING")
print("PVO_SYSTEM_ID   :", os.getenv('PVO_SYSTEM_ID') or "MISSING")
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

def test_endpoint(path, label):
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"{label} → {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status : {r.status_code}")
        if r.status_code != 200:
            print("Réponse non-JSON :", r.text[:200])
            return None
        data = r.json()
        print("Réponse :", data)
        if data.get('code') == 0:
            print(f"SUCCÈS {label} ! Data :", data.get('data'))
            return data['data']
        else:
            print(f"Erreur {label} :", data.get('msg') or data)
    except Exception as e:
        print(f"Erreur {label} :", str(e))
    return None

def try_get_power():
    # Tentative 1 : endpoint basique ECU status (souvent accessible en Lv0)
    data = test_endpoint(f'/ecu/{ECU_ID}', "ECU Status")
    if data:
        power = data.get('power') or data.get('current_power') or data.get('output_power')
        if power:
            print(f"Power trouvée : {power} W")
            return float(power)

    # Tentative 2 : realtime global (rare mais parfois OK)
    data = test_endpoint('/systems/realtime', "Realtime global")
    if data:
        power = data.get('power') or data.get('current_power')
        if power:
            print(f"Power globale trouvée : {power} W")
            return float(power)

    print("Aucune puissance récupérée")
    return None

def push_to_pvoutput(power_w):
    if power_w is None:
        print("Skip push : pas de puissance")
        return
    date_str = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H:%M')
    url = 'https://pvoutput.org/service/r2/addstatus.jsp'
    params = {
        'd': date_str,
        't': time_str,
        'v2': int(power_w),  # Puissance actuelle comme Peak Power
        'c1': 0,             # Pas d'énergie journalière
        'm': 'Puissance instantanée Lv0 (test)'
    }
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=params, headers=headers)
        print("PVOutput réponse :", r.text.strip())
        if "OK" in r.text.upper():
            print("Push puissance actuelle OK !")
        else:
            print("Échec push")
    except Exception as e:
        print("Erreur push :", str(e))

if __name__ == '__main__':
    print("Démarrage - Test Lv0 limité (power realtime & list)")
    test_endpoint('/user/api/v2/ecu/list', "Liste ECU")
    test_endpoint('/ecu/status', "ECU Status simple")
    power = try_get_power()
    push_to_pvoutput(power)
    print("Fin")
