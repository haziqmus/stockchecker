import requests
import os
from datetime import datetime, timedelta

target_plan = os.environ.get("TARGET_PLAN")
target_region = os.environ.get("TARGET_REGION")
custom_message_template = os.environ.get("NOTIFICATION_MESSAGE")
preorder_message_template = os.environ.get("PREORDER_NOTIFICATION_MESSAGE")
button_text = os.environ.get("BUTTON_TEXT")
button_url = os.environ.get("BUTTON_URL")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

STATE_FILE = "last_notification.txt"
COOLDOWN_HOURS = 12

def send_telegram_message(message, button_text=None, button_url=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Telegram credentials not found.")
        return

    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    
    if button_text and button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {
                    "text": button_text,
                    "url": button_url
                }
            ]]
        }
    
    try:
        response = requests.post(send_url, json=payload)
        if response.status_code == 200 and response.json().get("ok"):
            print("Telegram message sent successfully!")
        else:
            print(f"Telegram API error: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def can_send_notification():
    if not os.path.exists(STATE_FILE):
        return True
    
    try:
        with open(STATE_FILE, 'r') as f:
            last_time_str = f.read().strip()
            last_time = datetime.fromisoformat(last_time_str)
            time_diff = datetime.now() - last_time
            
            if time_diff >= timedelta(hours=COOLDOWN_HOURS):
                return True
            else:
                remaining = timedelta(hours=COOLDOWN_HOURS) - time_diff
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                print(f"Cooldown active. Next notification in {hours}h {minutes}m")
                return False
    except Exception as e:
        print(f"Error reading state file: {e}")
        return True

def update_notification_time():
    try:
        with open(STATE_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(f"Error writing state file: {e}")

def clear_notification_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
            print("Cooldown cleared - back to normal 10-minute checks")
        except Exception as e:
            print(f"Error removing state file: {e}")

def check_stock():
    if not target_plan or not target_region:
        print("Error: TARGET_PLAN or TARGET_REGION not found in GitHub Secrets.")
        return

    url = f"https://ca.api.ovh.com/v1/vps/order/rule/datacenter?ovhSubsidiary=WE&planCode={target_plan}"
    print(f"Checking Linux stock for {target_plan} in {target_region} only...")
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"API Error: {response.status_code}")
            return

        data = response.json()
        found_stock = False
        found_preorder = False
        
        if 'datacenters' in data:
            for dc in data['datacenters']:
                if dc['datacenter'] == target_region:
                    linux_status = dc.get('linuxStatus', 'out-of-stock')
                    
                    if linux_status == 'out-of-stock-preorder-allowed':
                        found_preorder = True
                        print(f"Found {target_region} with Linux Status: {linux_status}")
                    elif linux_status != 'out-of-stock':
                        found_stock = True
                        print(f"Found {target_region} with Linux Status: {linux_status}")

        if found_preorder and not found_stock:
            if can_send_notification():
                if preorder_message_template:
                    msg = preorder_message_template.replace("{plan}", target_plan).replace("{region}", target_region)
                else:
                    msg = f"PREORDER AVAILABLE (Linux)!\n\nPlan: {target_plan}\nLocation: {target_region}\nStatus: out-of-stock-preorder-allowed"
                
                print(msg)
                btn_text = button_text if button_text else "Order Now 🛒"
                btn_url = button_url if button_url else "https://www.ovhcloud.com/asia/vps/"
                send_telegram_message(msg, btn_text, btn_url)
                update_notification_time()
            else:
                print("Preorder still available but in cooldown period")
        elif found_stock:
            if custom_message_template:
                msg = custom_message_template.replace("{plan}", target_plan).replace("{region}", target_region)
            else:
                msg = f"STOCK FOUND (Linux)!\n\nPlan: {target_plan}\nLocation: {target_region}"
            
            print(msg)
            
            if can_send_notification():
                btn_text = button_text if button_text else "Order Now 🛒"
                btn_url = button_url if button_url else "https://www.ovhcloud.com/asia/vps/"
                send_telegram_message(msg, btn_text, btn_url)
                update_notification_time()
            else:
                print("Stock still available but in cooldown period - message not sent")
        else:
            print(f"No Linux stock available in {target_region}.")
            clear_notification_state()

    except Exception as e:
        print(f"Script Error: {e}")

if __name__ == "__main__":
    check_stock()
