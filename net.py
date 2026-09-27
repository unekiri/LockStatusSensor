"""Wi-Fi 接続と時刻同期。ESP32 専用（network / ntptime は MicroPython のみ）。"""

import time


def connect_wifi(config, timeout_s=20):
    """接続できたら WLAN を返す。時間内に繋がらなければ OSError。"""
    import network

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan

    print("Wi-Fi に接続中:", config["ssid"])
    wlan.connect(config["ssid"], config["password"])

    deadline = time.time() + timeout_s
    while not wlan.isconnected():
        if time.time() > deadline:
            raise OSError("Wi-Fi に接続できません: " + config["ssid"])
        time.sleep(0.5)

    print("Wi-Fi 接続:", wlan.ifconfig()[0])
    return wlan


def sync_time():
    """NTP で時刻を合わせる。合えば True。

    ESP32 の time.time() は電源投入時 2000-01-01 から始まる。同期しないまま
    送ると、ブラウザ側の「最終更新」が 2000 年と表示されて嘘になるので、
    同期できなかった場合は ts を送らない（sender.py 側で判断する）。
    """
    try:
        import ntptime

        ntptime.settime()
        print("NTP 同期:", time.localtime())
        return True
    except Exception as e:
        print("NTP 同期に失敗:", e)
        return False


# MicroPython の epoch は 2000-01-01、CPython は 1970-01-01。どちらで動いて
# いるかは gmtime(0) が返す年で確定できる。time.time() の値の大小で推測すると
# 2031-09-09 以降に判定が逆転するので、そこには頼らない。
_EPOCH_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0


def unix_time():
    """Unix epoch 秒。ブラウザ側が new Date(ts * 1000) で使う。"""
    return int(time.time()) + _EPOCH_OFFSET
