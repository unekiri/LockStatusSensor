"""位置出し用。接点の生の状態をそのまま流し続ける。

リードスイッチを取り付ける前に、これを走らせたまま磁石を手に持って近づけ、
どの距離・どの向きで閉じるかを目で確認する。

    mpremote run check_wiring.py
"""

import json
import time

from machine import Pin

from lock_sensor import classify

gpio = json.load(open("config.json"))["gpio"]

locked = Pin(gpio["locked_pin"], Pin.IN, Pin.PULL_UP)
unlocked = Pin(gpio["unlocked_pin"], Pin.IN, Pin.PULL_UP)

print("A=GPIO{}  B=GPIO{}".format(gpio["locked_pin"], gpio["unlocked_pin"]))

while True:
    a = locked.value() == 0
    b = unlocked.value() == 0
    print(
        "A={}  B={}  -> {}".format(
            "閉" if a else "開", "閉" if b else "開", classify(a, b)
        )
    )
    time.sleep(0.3)
