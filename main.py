import requests
import time
import hmac
import hashlib
import base64
import uuid
import os
from datetime import datetime

# Env vars from Render
APP_ID = os.getenv('APS_APP_ID')
APP_SECRET = os.getenv('APS_APP_SECRET')
PVO_API_KEY = os.getenv('PVO_API_KEY')
PVO_SYSTEM_ID = os.getenv('PVO_SYSTEM_ID')

BASE_URL = 'https://openapi.apsystems.com'  # base officielle

def generate_signature(method, path, timestamp, nonce):
    string_to_sign = f"{timestamp}/{nonce}/{APP_ID}/{path}/{method.upper()}/HmacSHA256"
    mac = hmac.new(APP_SECRET.encode(), string_to_sign.encode(), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

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
    path = f'/systems/summary/{SYSTEM_SID}'  # endpoint probable pour daily (vérifie manuel si /energy ou /production)
    url = BASE_URL + path
    headers = get_headers(path)
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get('code') == 0:
            # Ajuste selon structure réelle (ex: data['data']['today_energy_kwh'] ou 'energy_today')
            today_kwh = data['data'].get('today_energy') or data['data'].get('energy_today')  # adapte après test
            return float(today_kwh) if today_kwh else None
        else:
            print("API error:", data)
    except Exception as e:
        print("Request failed:", e)
    return None

def push_pvoutput(energy_kwh):
    if energy_kwh is None:
        return
    energy_wh = int(energy_kwh * 1000)  # to Wh
    date_str = datetime.now().strftime('%Y%m%d')
    url = 'https://pvoutput.org/service/r2/addoutput.jsp'
    params = {
        'd': date_str,
        'c1': energy_wh,  # Energy Generation
        # 'v2': peak_power if available later
    }
    headers = {
        'X-Pvoutput-Apikey': PVO_API_KEY,
        'X-Pvoutput-SystemId': PVO_SYSTEM_ID,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    r = requests.post(url, data=params, headers=headers)
    print("PVOutput response:", r.text)

if __name__ == '__main__':
    energy = get_today_energy()
    if energy:
        push_pvoutput(energy)
