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

# Variables fixes
SYSTEM_SID = 'D24C931099345673'
ECU_ID = '215000085900'

# Variables d'environnement
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

def test_api_list():
    path = '/user/api/v2/systems'  # ou /ecu/list pour lister les systèmes/ECU autorisés
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"Test list endpoint : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"List status code : {r.status_code}")
        data = r.json()
        print("Réponse list complète :", data)
        return data
    except Exception as e:
        print("Erreur list :", str(e))
        return None

def get_today_energy():
    # Test 1 : path original avec SID
    path_sid = f'/user/api/v2/systems/summary/{SYSTEM_SID}'
    url_sid = BASE_URL + path_sid
    headers = get_headers(path_sid)
    try:
        print(f"Appel summary SID : {url_sid}")
        r = requests.get(url_sid, headers=headers, timeout=15)
        print(f"Status code SID : {r.status_code}")
        data = r.json()
        print("Réponse summary SID :", data)
        if data.get('code') == 0:
            today_kwh = data['data'].get('today') or data['data'].get('energy_today') or data['data'].get('today_energy')
            if today_kwh is not None:
                print(f"Énergie today trouvée (SID) : {today_kwh} kWh")
                return float(today_kwh)
        else:
            print("Erreur summary SID :", data.get('msg') or data)
    except Exception as e:
        print("Erreur summary SID :", str(e))

    # Test 2 : path alternatif avec ECU_ID (souvent plus fiable pour energy)
    path_ecu = f'/user/api/v2/ecu/{ECU_ID}/energy/today'  # ou /energy/daily
    url_ecu = BASE_URL + path_ecu
    headers = get_headers(path_ecu)
    try:
        print(f"Appel energy ECU : {url_ecu}")
        r = requests.get(url_ecu, headers=headers, timeout=15)
        print(f"Status code ECU : {r.status_code}")
        data = r.json()
        print("Réponse energy ECU :", data)
        if data.get('code') == 0:
            today_kwh = data['data'].get('today') or data['data'].get('energy') or data['data'].get('today_energy')
            if today_kwh is not None:
                print(f"Énergie today trouvée (ECU) : {today_kwh} kWh")
                return float(today_kwh)
        else:
            print("Erreur energy ECU :", data.get('msg') or data)
    except Exception as e:
        print("Erreur energy ECU :", str(e))

    return None

def push_pvoutput(energy_kwh):
    if energy_kwh is None:
        print("Aucune énergie à envoyer → skip push")
        return
    energy_wh = int(float(energy_kwh) * 1000)
    date_str = datetime.now().strftime('%Y%m%d')
    url = 'https://pvoutput.org/service/r2/addoutput.jsp'
    params = {
        'd': date_str,
        'c1': energy_wh,
    }
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    try:
        r = requests.post(url, data=params, headers=headers)
        print("Réponse PVOutput :", r.text.strip())
        if r.status_code == 200 and "OK" in r.text.upper():
            print("Push PVOutput réussi !")
        else:
            print("Échec push PVOutput")
    except Exception as e:
        print("Erreur push :", str(e))

if __name__ == '__main__':
    print("Démarrage script APsystems → PVOutput")
    test_api_list()  # Test list pour voir si SID visible
    energy = get_today_energy()
    push_pvoutput(energy)
    print("Fin exécution")
