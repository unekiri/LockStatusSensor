"""サムターンの回転位置を2個のリードスイッチで読み取る。

配線（Raspberry Pi、内部プルアップ使用）:

    GPIO17 ---- リードスイッチA（施錠位置） ---- GND
    GPIO27 ---- リードスイッチB（解錠位置） ---- GND

サムターンに磁石を1個貼り付け、施錠位置でAが、解錠位置でBが閉じるように
固定側へスイッチを配置する。磁石が近い = 接点が閉じる = ピンがLOW。

2個使うのは「解錠」と「センサ異常」を区別するため。1個だけだと磁石が
落ちた場合もサムターンが途中で止まっている場合も同じ「施錠位置ではない」
にしか見えず、施錠されていないものを解錠と断定してしまう。
"""

from enum import Enum


class LockState(str, Enum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    UNKNOWN = "unknown"


def classify(locked_closed: bool, unlocked_closed: bool) -> LockState:
    """2接点の状態を施錠状態に変換する。

    両方開 = サムターンが中間位置、磁石の脱落、断線のいずれか。
    両方閉 = 配線ミスか磁石の位置ずれ。どちらも状態を断定できないため UNKNOWN。
    """
    if locked_closed and not unlocked_closed:
        return LockState.LOCKED
    if unlocked_closed and not locked_closed:
        return LockState.UNLOCKED
    return LockState.UNKNOWN


class GpioLockSensor:
    """gpiozero 経由で実際のリードスイッチを読む。"""

    def __init__(self, locked_pin: int, unlocked_pin: int, bounce_seconds: float):
        from gpiozero import Button

        # pull_up=True で内部プルアップを有効化。スイッチは GPIO と GND の間に入れる。
        # bounce_time がリードスイッチのチャタリングを吸収する。
        self._locked = Button(locked_pin, pull_up=True, bounce_time=bounce_seconds)
        self._unlocked = Button(unlocked_pin, pull_up=True, bounce_time=bounce_seconds)

    def read(self) -> LockState:
        return classify(self._locked.is_pressed, self._unlocked.is_pressed)

    def close(self) -> None:
        self._locked.close()
        self._unlocked.close()


class MockLockSensor:
    """GPIO のない開発機用。mock_state ファイルの中身をそのまま状態として返す。

    echo locked > mock_state のように書き換えると状態遷移を再現できる。
    """

    def __init__(self, path: str = "mock_state"):
        self._path = path

    def read(self) -> LockState:
        try:
            with open(self._path) as f:
                raw = f.read().strip()
        except FileNotFoundError:
            return LockState.UNKNOWN

        try:
            return LockState(raw)
        except ValueError:
            return LockState.UNKNOWN

    def close(self) -> None:
        pass


def create_sensor(config: dict):
    gpio = config["gpio"]
    if gpio.get("mock", False):
        return MockLockSensor(gpio.get("mock_state_file", "mock_state"))
    return GpioLockSensor(
        locked_pin=gpio["locked_pin"],
        unlocked_pin=gpio["unlocked_pin"],
        bounce_seconds=gpio.get("bounce_seconds", 0.05),
    )
