from lock_sensor import (
    LOCKED,
    UNKNOWN,
    UNLOCKED,
    Debounced,
    MockLockSensor,
    classify,
)


def test_classify_locked():
    assert classify(locked_closed=True, unlocked_closed=False) == LOCKED


def test_classify_unlocked():
    assert classify(locked_closed=False, unlocked_closed=True) == UNLOCKED


def test_both_open_is_unknown():
    # 中間位置・磁石脱落・断線。解錠と断定してはいけない。
    assert classify(locked_closed=False, unlocked_closed=False) == UNKNOWN


def test_both_closed_is_unknown():
    # 配線ミスか磁石の位置ずれ。
    assert classify(locked_closed=True, unlocked_closed=True) == UNKNOWN


def test_debounce_holds_until_stable():
    d = Debounced(bounce_ms=50)
    assert d.update(LOCKED, 0) == LOCKED           # 初回は即確定
    assert d.update(UNKNOWN, 10) == LOCKED         # バタつきは通さない
    assert d.update(UNKNOWN, 40) == LOCKED         # まだ 50ms 経っていない
    assert d.update(UNKNOWN, 60) == UNKNOWN        # 50ms 続いたので確定


def test_debounce_restarts_when_value_flips_back():
    d = Debounced(bounce_ms=50)
    d.update(LOCKED, 0)
    d.update(UNKNOWN, 10)
    d.update(LOCKED, 30)                      # 戻ったのでタイマーはリセット
    assert d.update(UNKNOWN, 70) == LOCKED    # ここから数え直しになる
    assert d.update(UNKNOWN, 110) == LOCKED   # 70 から数えてまだ 40ms
    assert d.update(UNKNOWN, 125) == UNKNOWN  # 50ms 続いたので確定


def test_debounce_survives_ticks_wraparound():
    # MicroPython の ticks_ms は一定値で 0 に戻る。負の経過時間で
    # 確定が止まってしまわないことを見る。
    d = Debounced(bounce_ms=50)
    d.update(LOCKED, (1 << 30) - 10)
    d.update(UNLOCKED, (1 << 30) - 5)
    assert d.update(UNLOCKED, 60) == UNLOCKED


def test_mock_sensor_reads_file(tmp_path):
    path = tmp_path / "mock_state"
    path.write_text("locked\n")
    assert MockLockSensor(str(path)).read() == LOCKED


def test_mock_sensor_missing_file_is_unknown(tmp_path):
    assert MockLockSensor(str(tmp_path / "absent")).read() == UNKNOWN


def test_mock_sensor_garbage_is_unknown(tmp_path):
    path = tmp_path / "mock_state"
    path.write_text("opened")
    assert MockLockSensor(str(path)).read() == UNKNOWN
