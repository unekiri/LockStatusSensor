import time
import paho.mqtt.client as mqtt
import random
import json
import os

def load_config():
    # 設定ファイルが存在しない場合はサンプルをコピー
    if not os.path.exists('config.json'):
        if os.path.exists('config.example.json'):
            import shutil
            shutil.copy('config.example.json', 'config.json')
            print('config.jsonを作成しました。必要に応じて設定を変更してください。')
        else:
            raise FileNotFoundError('config.jsonまたはconfig.example.jsonが見つかりません。')
    
    with open('config.json', 'r') as f:
        return json.load(f)

# 設定の読み込み
config = load_config()
MQTT_BROKER = config['mqtt']['broker']
MQTT_PORT = config['mqtt']['port']
MQTT_TOPIC = config['mqtt']['topic']
MQTT_CLIENT_ID = config['mqtt']['client_id']

# 前回の状態を保存
last_state = None

def connect_mqtt():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT)
    print('MQTTブローカーに接続成功')
    return client

def read_sensor():
    # テスト用にランダムな状態を生成
    return random.randint(0, 1)  # 1: 施錠状態, 0: 解錠状態

def main():
    global last_state
    mqtt_client = connect_mqtt()
    
    try:
        while True:
            current_state = read_sensor()
            
            # 状態が変化した場合のみ送信
            if current_state != last_state:
                if current_state == 1:
                    message = "locked"
                else:
                    message = "opened"
                
                try:
                    mqtt_client.publish(MQTT_TOPIC, message)
                    print(f"状態を送信: {message}")
                except Exception as e:
                    print(f"送信エラー: {e}")
                    # 再接続を試みる
                    try:
                        mqtt_client = connect_mqtt()
                    except:
                        print("再接続に失敗しました")
                
                last_state = current_state
            
            time.sleep(5)  # 5秒ごとに状態をチェック
            
    except KeyboardInterrupt:
        print("プログラムを終了します")
        mqtt_client.disconnect()

if __name__ == "__main__":
    main() 