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
    # Test 1 : ECU realtime (souvent le plus accessible)
    path_realtime = f'/ecu/{ECU_ID}/realtime'
    data_rt = test_endpoint(path_realtime)
    if data_rt and data_rt.get('code') == 0:
        # Exemple parsing power actuelle (pas daily, mais test accès)
        power = data_rt['data'].get('power') or data_rt['data'].get('current_power')
        if power:
            print(f"Power actuelle trouvée : {power} W")
    
    # Test 2 : ECU production daily
    path_daily = f'/ecu/{ECU_ID}/production/daily'
    data_daily = test_endpoint(path_daily)
    if data_daily and data_daily.get('code') == 0:
        today_kwh = data_daily['data'].get('today') or data_daily['data'].get('energy_today')
        if today_kwh:
            print(f"Énergie today trouvée : {today_kwh} kWh")
            return float(today_kwh)
    
    # Test 3 : fallback summary
    path_summary = f'/user/api/v2/systems/summary/{SYSTEM_SID}'
    data_summary = test_endpoint(path_summary)
    if data_summary and data_summary.get('code') == 0:
        today_kwh = data_summary['data'].get('today') or data_summary['data'].get('energy_today')
        if today_kwh:
            print(f"Énergie today trouvée (summary) : {today_kwh} kWh")
            return float(today_kwh)
    
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
