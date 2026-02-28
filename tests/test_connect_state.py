from cs_caller.gui.connect_state import ConnectAttemptTracker, build_connect_controls


def test_build_connect_controls_for_idle_disconnected() -> None:
    controls = build_connect_controls(connecting=False, connected=False)
    assert controls.connect_enabled is True
    assert controls.cancel_enabled is False
    assert controls.connect_button_text == "连接源"


def test_build_connect_controls_for_connecting_state() -> None:
    controls = build_connect_controls(connecting=True, connected=False)
    assert controls.connect_enabled is False
    assert controls.cancel_enabled is True
    assert controls.connect_button_text == "连接中..."


def test_build_connect_controls_for_idle_connected() -> None:
    controls = build_connect_controls(connecting=False, connected=True)
    assert controls.connect_enabled is True
    assert controls.cancel_enabled is False
    assert controls.connect_button_text == "重连源"


def test_connect_attempt_tracker_cancel_and_ignore_stale_finish() -> None:
    tracker = ConnectAttemptTracker()
    first = tracker.start()
    assert tracker.is_connecting is True
    assert tracker.active_attempt_id == first

    cancelled = tracker.cancel()
    assert cancelled == first
    assert tracker.is_connecting is False
    assert tracker.active_attempt_id is None

    # 旧回调不应篡改状态
    assert tracker.finish(first) is False
    assert tracker.is_connecting is False


def test_connect_attempt_tracker_finish_only_active_attempt() -> None:
    tracker = ConnectAttemptTracker()
    first = tracker.start()
    second = tracker.start()

    assert tracker.finish(first) is False
    assert tracker.is_connecting is True
    assert tracker.active_attempt_id == second

    assert tracker.finish(second) is True
    assert tracker.is_connecting is False
