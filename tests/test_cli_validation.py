import pytest

from cs_caller.app_settings import AppSettings
from cs_caller.cli import _resolve_gui_runtime_settings, validate_source_mode_args


def test_validate_source_mode_args_accepts_valid_inputs() -> None:
    assert validate_source_mode_args("mock", "C:/maps/minimap.png") == "mock"
    assert validate_source_mode_args("ndi", "ndi://OBS") == "ndi"
    assert validate_source_mode_args("capture", "0") == "capture"


def test_validate_source_mode_args_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="未知 source mode"):
        validate_source_mode_args("bad", "x")


def test_validate_source_mode_args_rejects_missing_source_by_mode() -> None:
    with pytest.raises(ValueError, match="mock 模式需要图片路径"):
        validate_source_mode_args("mock", "")
    with pytest.raises(ValueError, match="ndi 模式需要 --source"):
        validate_source_mode_args("ndi", "")
    with pytest.raises(ValueError, match="capture 模式需要 --source"):
        validate_source_mode_args("capture", "")


def test_validate_source_mode_args_allow_empty_source() -> None:
    assert validate_source_mode_args("mock", "", allow_empty_source=True) == "mock"
    assert validate_source_mode_args("ndi", "", allow_empty_source=True) == "ndi"
    assert validate_source_mode_args("capture", "", allow_empty_source=True) == "capture"


def test_validate_source_mode_args_normalizes_case_and_whitespace() -> None:
    assert validate_source_mode_args("  NDI ", " ndi://OBS ") == "ndi"


def test_resolve_gui_runtime_settings_keeps_detect_toggle_from_settings() -> None:
    class Args:
        source_mode = None
        image = None
        source = None
        map = None
        tts_backend = None

    settings = AppSettings(
        map_name="de_dust2",
        source_mode="capture",
        source="0",
        tts_backend="auto",
        detect_enabled=True,
    )
    resolved = _resolve_gui_runtime_settings(Args(), settings)
    assert resolved == ("capture", "0", "de_dust2", "auto", True)
