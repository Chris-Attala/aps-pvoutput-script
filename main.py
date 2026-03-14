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

# Variables fixes
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

def test_api_list():
    path = '/ecu/list' # Liste tous les systèmes visibles pour cet App ID
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        print(f"Test list systèmes : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status list : {r.status_code}")
        data = r.json()
        print("Réponse list complète :", data)
        if data.get('code') == 0:
            print("Systèmes visibles :", data.get('data'))
        else:
            print("Erreur list :", data.get('msg') or data)
    except Exception as e:
        print("Erreur list :", str(e))

def get_today_energy():
    # Test 1 : ECU summary (le plus prometteur du manuel)
    path_ecu_summary = f'/user/api/v2/systems/{SYSTEM_SID}/devices/ecu/summary/{ECU_ID}'
    url = BASE_URL + path_ecu_summary
    headers = get_headers(path_ecu_summary)
    try:
        print(f"Test ECU summary : {url}")
        r = requests.get(url, headers=headers, timeout=15)
        print(f"Status ECU summary : {r.status_code}")
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
        print("Erreur ECU summary :", str(e))

    # Test 2 : Realtime ECU (souvent accessible même en Lv0)
    path_realtime = f'/ecu/{ECU_ID}/realtime'
    url_rt = BASE_URL + path_realtime
    headers_rt = get_headers(path_realtime)
    try:
        print(f"Test realtime ECU : {url_rt}")
        r = requests.get(url_rt, headers=headers_rt, timeout=15)
        print(f"Status realtime : {r.status_code}")
        data_rt = r.json()
        print("Réponse realtime :", data_rt)
        if data_rt.get('code') == 0:
            power = data_rt['data'].get('power') or data_rt['data'].get('current_power')
            if power:
                print(f"Power actuelle : {power} W")
    except Exception as e:
        print("Erreur realtime :", str(e))

    return None  # On n'a pas encore la daily, on arrête là pour ce test

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
    test_api_list()  # Vérifie quels systèmes/ECU sont visibles
    energy = get_today_energy()
    push_pvoutput(energy)
    print("Fin")
