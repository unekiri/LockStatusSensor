"""施錠状態を MQTT に publish する常駐スクリプト。

publish するトピックは2つ:

  lock/status        retain付きJSON。 {"state": "locked"|"unlocked"|"unknown", "ts": ...}
  lock/availability  retain付き "online" / "offline"（offline は LWT でブローカーが送る）

retain を付けるのは、ブラウザが後から接続しても最新状態を受け取れるようにするため。
availability を分けるのは、「施錠中のまま送信が止まった」と「本当に今も施錠中」を
受信側が区別できるようにするため。
"""

import json
import logging
import os
import shutil
import signal
import threading
import time

import paho.mqtt.client as mqtt

from lock_sensor import LockState, create_sensor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("lockstatus")

CONFIG_PATH = "config.json"
EXAMPLE_CONFIG_PATH = "config.example.json"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        if not os.path.exists(EXAMPLE_CONFIG_PATH):
            raise FileNotFoundError(
                f"{CONFIG_PATH} も {EXAMPLE_CONFIG_PATH} も見つかりません。"
            )
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        logger.info("%s を作成しました。設定を確認してください。", CONFIG_PATH)

    with open(CONFIG_PATH) as f:
        return json.load(f)


def build_client(config: dict, reconnected: threading.Event) -> mqtt.Client:
    mqtt_config = config["mqtt"]
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=mqtt_config["client_id"],
    )

    username = mqtt_config.get("username")
    if username:
        client.username_pw_set(username, mqtt_config.get("password"))

    # 接続が切れたらブローカーが代わりに offline を流す。センサーの突然死を検知できる。
    client.will_set(
        mqtt_config["availability_topic"],
        payload="offline",
        qos=1,
        retain=True,
    )

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        if reason_code == 0:
            logger.info("MQTTブローカーに接続しました")
            _client.publish(
                mqtt_config["availability_topic"], "online", qos=1, retain=True
            )
            # 切断中に状態が変わっていた可能性があるので、接続のたびに送り直させる。
            reconnected.set()
        else:
            logger.error("MQTT接続に失敗しました: %s", reason_code)

    def on_disconnect(_client, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            logger.warning("MQTT接続が切れました (%s)。再接続します。", reason_code)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    return client


def publish_state(client: mqtt.Client, topic: str, state: LockState) -> bool:
    """送信できたら True。失敗を握りつぶすと未送信の状態が送信済み扱いになる。"""
    # 未接続時に publish すると paho が QoS1 を内部キューに積み、こちらの再送と
    # 二重に届く。接続できるまでは送らず、再接続時にまとめて送り直す。
    if not client.is_connected():
        return False

    payload = json.dumps(
        {"state": state.value, "ts": int(time.time())},
        ensure_ascii=False,
    )
    result = client.publish(topic, payload, qos=1, retain=True)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.warning("publish に失敗しました (rc=%s)。次の周期で再送します。", result.rc)
        return False
    logger.info("状態を送信: %s", payload)
    return True


def main() -> None:
    config = load_config()
    mqtt_config = config["mqtt"]
    poll_seconds = config.get("poll_seconds", 1.0)
    heartbeat_seconds = config.get("heartbeat_seconds", 60)

    sensor = create_sensor(config)
    reconnected = threading.Event()
    client = build_client(config, reconnected)

    running = True

    def handle_signal(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # loop_start がバックグラウンドで再接続まで面倒を見る。
    client.connect_async(mqtt_config["broker"], mqtt_config["port"], keepalive=30)
    client.loop_start()

    last_state = None
    last_publish = 0.0

    try:
        while running:
            state = sensor.read()
            now = time.monotonic()

            # 変化時に加えて定期的にも送る。retain が消えた場合の保険と、
            # 受信側が ts で鮮度を判断できるようにするため。
            due = (
                state != last_state
                or reconnected.is_set()
                or now - last_publish >= heartbeat_seconds
            )
            if due:
                reconnected.clear()
                if publish_state(client, mqtt_config["topic"], state):
                    last_state = state
                    last_publish = now
                else:
                    # 送信済みにしない。次の周期で同じ状態をもう一度試す。
                    last_state = None

            time.sleep(poll_seconds)
    finally:
        logger.info("終了します")
        client.publish(
            mqtt_config["availability_topic"], "offline", qos=1, retain=True
        )
        client.loop_stop()
        client.disconnect()
        sensor.close()


if __name__ == "__main__":
    main()
