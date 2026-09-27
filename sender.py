"""施錠状態を MQTT に publish する常駐スクリプト（ESP32 / MicroPython）。

publish するトピックは2つ:

  lock/status        retain付きJSON。 {"state": "locked"|"unlocked"|"unknown", "ts": ...}
  lock/availability  retain付き "online" / "offline"（offline は LWT でブローカーが送る）

retain を付けるのは、ブラウザが後から接続しても最新状態を受け取れるようにするため。
availability を分けるのは、「施錠中のまま送信が止まった」と「本当に今も施錠中」を
受信側が区別できるようにするため。

QoS は 0 で送っている。umqtt の qos=1 はブローカーが応答しないとソケット待ちで
止まってしまい、ドアに付けた端末では復帰できなくなる。代わりに retain と
heartbeat_seconds ごとの再送で届かせる。最悪ケースでは heartbeat 1回ぶん表示が
古くなり、その後 keepalive 切れで LWT が飛んで「不明」に落ちる。
"""

import json
import time

from umqtt.simple import MQTTClient

import net
from lock_sensor import create_sensor

CONFIG_PATH = "config.json"


def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except OSError:
        raise OSError(
            CONFIG_PATH + " がありません。config.example.json を編集して "
            "config.json として端末に転送してください。"
        )


class Link:
    """MQTT 接続を1本だけ持ち、切れたら捨てて張り直す。"""

    def __init__(self, config):
        self._config = config
        self._client = None

    def _build(self):
        config = self._config
        client = MQTTClient(
            config["client_id"],
            config["broker"],
            port=config["port"],
            user=config.get("username") or None,
            password=config.get("password") or None,
            keepalive=config.get("keepalive_seconds", 180),
        )
        # 接続が切れたらブローカーが代わりに offline を流す。突然死を検知できる。
        client.set_last_will(
            config["availability_topic"], b"offline", retain=True, qos=0
        )
        return client

    def ensure_connected(self):
        """つなぎ直したときだけ True。呼び出し側はそこで状態を送り直す。"""
        if self._client is not None:
            return False

        client = self._build()
        client.connect()
        self._client = client
        print("MQTTブローカーに接続しました")
        client.publish(
            self._config["availability_topic"], b"online", retain=True, qos=0
        )
        return True

    def publish(self, topic, payload):
        if self._client is None:
            return False
        try:
            self._client.publish(topic, payload, retain=True, qos=0)
            return True
        except OSError as e:
            print("publish に失敗しました:", e, "。つなぎ直します。")
            self.drop()
            return False

    def drop(self):
        if self._client is None:
            return
        try:
            self._client.disconnect()
        except OSError:
            pass
        self._client = None


def build_payload(state, time_synced):
    body = {"state": state}
    if time_synced:
        body["ts"] = net.unix_time()
    return json.dumps(body)


def main():
    config = load_config()
    mqtt_config = config["mqtt"]
    poll_ms = int(config.get("poll_seconds", 0.2) * 1000)
    heartbeat_ms = int(config.get("heartbeat_seconds", 60) * 1000)

    wlan = net.connect_wifi(config["wifi"])
    time_synced = net.sync_time()

    sensor = create_sensor(config)
    link = Link(mqtt_config)

    last_state = None
    last_publish = time.ticks_ms()

    while True:
        if not wlan.isconnected():
            print("Wi-Fi が切れました。再接続します。")
            link.drop()
            try:
                wlan = net.connect_wifi(config["wifi"])
            except OSError as e:
                print(e)
                time.sleep(2)
                continue
            if not time_synced:
                time_synced = net.sync_time()

        try:
            # 切断中に状態が変わっていた可能性があるので、接続のたびに送り直す。
            reconnected = link.ensure_connected()
        except OSError as e:
            print("MQTTブローカーに接続できません:", e)
            link.drop()
            time.sleep(2)
            continue

        state = sensor.read(time.ticks_ms())
        now = time.ticks_ms()

        # 変化時に加えて定期的にも送る。retain が消えた場合の保険と、
        # ブローカーの keepalive を維持するため。
        due = (
            state != last_state
            or reconnected
            or time.ticks_diff(now, last_publish) >= heartbeat_ms
        )
        if due:
            payload = build_payload(state, time_synced)
            if link.publish(mqtt_config["topic"], payload):
                print("状態を送信:", payload)
                last_state = state
                last_publish = now
            else:
                # 送信済みにしない。次の周期で同じ状態をもう一度試す。
                last_state = None

        time.sleep_ms(poll_ms)
