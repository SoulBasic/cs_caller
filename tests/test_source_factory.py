import pytest

from cs_caller.source_factory import (
    SourceFactoryError,
    build_source,
    map_source_factory_error,
)


def test_source_factory_rejects_empty_source() -> None:
    with pytest.raises(SourceFactoryError, match="需要源文本"):
        build_source("ndi", "")


def test_source_factory_rejects_bad_mode() -> None:
    with pytest.raises(SourceFactoryError, match="未知 source mode"):
        build_source("bad", "x")


def test_source_factory_rejects_negative_capture_index() -> None:
    with pytest.raises(SourceFactoryError, match="必须 >= 0"):
        build_source("capture", "-2")


def test_source_factory_ndi_runtime_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cs_caller.source_factory.check_ndi_python_module_available", lambda: (True, "ok"))
    monkeypatch.setattr("cs_caller.source_factory.check_ndi_runtime_available", lambda: (False, "缺失"))

    with pytest.raises(SourceFactoryError, match="缺失"):
        build_source("ndi", "ndi://OBS")


def test_source_factory_ndi_python_module_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cs_caller.source_factory.check_ndi_python_module_available", lambda: (False, "请安装"))

    with pytest.raises(SourceFactoryError, match="请安装"):
        build_source("ndi", "ndi://OBS")


def test_map_source_factory_error_uses_code_prefix() -> None:
    text = map_source_factory_error(
        SourceFactoryError("capture_index_invalid", "capture 摄像头编号无效"),
        mode="capture",
    )
    assert text.startswith("[capture] 采集编号错误:")


def test_map_source_factory_error_fallback_for_unknown_exception() -> None:
    text = map_source_factory_error(RuntimeError("boom"), mode="ndi")
    assert text == "[ndi] 连接失败: boom"
