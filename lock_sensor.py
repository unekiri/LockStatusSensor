"""サムターンの回転位置を2個のリードスイッチで読み取る。

配線（ESP32、内部プルアップ使用）:

    GPIO32 ---- リードスイッチA（施錠位置） ---- GND
    GPIO33 ---- リードスイッチB（解錠位置） ---- GND

サムターンに磁石を1個貼り付け、施錠位置でAが、解錠位置でBが閉じるように
固定側へスイッチを配置する。磁石が近い = 接点が閉じる = ピンが LOW。

2個使うのは「解錠」と「センサ異常」を区別するため。1個だと磁石が落ちた
場合もサムターンが途中で止まっている場合も同じ「施錠位置ではない」にしか
見えず、施錠されていないものを解錠と断定してしまう。

このモジュールは MicroPython と CPython の両方で import できる。machine を
使うのは GpioLockSensor の中だけなので、開発機でも classify() を単体テスト
できる。
"""

LOCKED = "locked"
UNLOCKED = "unlocked"
UNKNOWN = "unknown"


def classify(locked_closed, unlocked_closed):
    """2接点の状態を施錠状態に変換する。

    両方開 = サムターンが中間位置、磁石の脱落、断線のいずれか。
    両方閉 = 配線ミスか磁石の位置ずれ。どちらも状態を断定できないため UNKNOWN。
    """
    if locked_closed and not unlocked_closed:
        return LOCKED
    if unlocked_closed and not locked_closed:
        return UNLOCKED
    return UNKNOWN


class Debounced:
    """同じ値が bounce_ms 続いて初めて確定させる。

    MicroPython の Pin には gpiozero の bounce_time がないので自前で持つ。
    リードスイッチは接点が閉じる瞬間に数ミリ秒バタつく。
    """

    def __init__(self, bounce_ms):
        self._bounce_ms = bounce_ms
        self._stable = None
        self._candidate = None
        self._since = 0

    def update(self, value, now_ms):
        if self._stable is None:
            self._stable = value
            self._candidate = value
            self._since = now_ms
            return self._stable

        if value != self._candidate:
            self._candidate = value
            self._since = now_ms
        elif value != self._stable and _elapsed(self._since, now_ms) >= self._bounce_ms:
            self._stable = value

        return self._stable


def _elapsed(since_ms, now_ms):
    """ticks_ms のラップアラウンドを踏んでも負にならない経過時間。"""
    delta = now_ms - since_ms
    return delta if delta >= 0 else delta + (1 << 30)


class GpioLockSensor:
    """実際のリードスイッチを読む。"""

    def __init__(self, locked_pin, unlocked_pin, bounce_ms):
        from machine import Pin

        # PULL_UP なので、磁石が近づいて接点が閉じるとピンは 0 になる。
        self._locked = Pin(locked_pin, Pin.IN, Pin.PULL_UP)
        self._unlocked = Pin(unlocked_pin, Pin.IN, Pin.PULL_UP)
        self._debounce = Debounced(bounce_ms)

    def read(self, now_ms):
        raw = classify(self._locked.value() == 0, self._unlocked.value() == 0)
        return self._debounce.update(raw, now_ms)


class MockLockSensor:
    """GPIO のない環境用。mock_state ファイルの中身をそのまま状態として返す。

    echo locked > mock_state のように書き換えると状態遷移を再現できる。
    """

    def __init__(self, path="mock_state"):
        self._path = path

    def read(self, now_ms=0):
        try:
            with open(self._path) as f:
                raw = f.read().strip()
        except OSError:
            return UNKNOWN

        return raw if raw in (LOCKED, UNLOCKED, UNKNOWN) else UNKNOWN


def create_sensor(config):
    gpio = config["gpio"]
    if gpio.get("mock", False):
        return MockLockSensor(gpio.get("mock_state_file", "mock_state"))
    return GpioLockSensor(
        locked_pin=gpio["locked_pin"],
        unlocked_pin=gpio["unlocked_pin"],
        bounce_ms=gpio.get("bounce_ms", 50),
    )
