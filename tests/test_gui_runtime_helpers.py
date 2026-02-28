from cs_caller.runtime_helpers import autofill_source_text, build_operating_mode_hint


def test_autofill_source_text_keeps_existing_value() -> None:
    assert autofill_source_text("ndi", "  ndi://Custom  ") == "ndi://Custom"


def test_autofill_source_text_fills_ndi_and_capture_defaults() -> None:
    assert autofill_source_text("ndi", " ") == "ndi://OBS"
    assert autofill_source_text("capture", "") == "0"
    assert autofill_source_text("mock", "") == ""


def test_build_operating_mode_hint_by_connection_and_detect_state() -> None:
    assert (
        build_operating_mode_hint(
            source_mode="ndi",
            source_connected=False,
            detect_enabled=False,
        )
        == "当前模式: NDI 未连接（待连接）"
    )
    assert (
        build_operating_mode_hint(
            source_mode="capture",
            source_connected=True,
            detect_enabled=False,
        )
        == "当前模式: Capture 仅预览（检测已关闭）"
    )
    assert (
        build_operating_mode_hint(
            source_mode="mock",
            source_connected=True,
            detect_enabled=True,
        )
        == "当前模式: Mock 图片 播报模式（检测+语音）"
    )
