import pytest

from cs_caller.cli import validate_source_mode_args


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
