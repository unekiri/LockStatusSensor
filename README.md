# Lock Status Sensor

MQTTを使用して施錠状態を監視・送信するPythonスクリプト

## 必要条件

- Python 3.7以上
- MQTTブローカー（Mosquitto推奨）

## セットアップ

1. 依存パッケージのインストール:
```bash
pip install -r requirements.txt
```

2. 設定ファイルの準備:
```bash
cp config.example.json config.json
```

3. `config.json`を環境に合わせて編集

## 使用方法

```bash
python sender.py
```

## 設定項目

config.jsonの設定項目:

- mqtt.broker: MQTTブローカーのアドレス
- mqtt.port: MQTTブローカーのポート番号
- mqtt.topic: 施錠状態を送信するトピック
- mqtt.client_id: クライアントID

## ライセンス

MIT 