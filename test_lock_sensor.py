from lock_sensor import LockState, MockLockSensor, classify


def test_classify_locked():
    assert classify(locked_closed=True, unlocked_closed=False) is LockState.LOCKED


def test_classify_unlocked():
    assert classify(locked_closed=False, unlocked_closed=True) is LockState.UNLOCKED


def test_both_open_is_unknown():
    # 中間位置・磁石脱落・断線。解錠と断定してはいけない。
    assert classify(locked_closed=False, unlocked_closed=False) is LockState.UNKNOWN


def test_both_closed_is_unknown():
    # 配線ミスか磁石の位置ずれ。
    assert classify(locked_closed=True, unlocked_closed=True) is LockState.UNKNOWN


def test_mock_sensor_reads_file(tmp_path):
    path = tmp_path / "mock_state"
    path.write_text("locked\n")
    assert MockLockSensor(str(path)).read() is LockState.LOCKED


def test_mock_sensor_missing_file_is_unknown(tmp_path):
    assert MockLockSensor(str(tmp_path / "absent")).read() is LockState.UNKNOWN


def test_mock_sensor_garbage_is_unknown(tmp_path):
    path = tmp_path / "mock_state"
    path.write_text("opened")
    assert MockLockSensor(str(path)).read() is LockState.UNKNOWN
