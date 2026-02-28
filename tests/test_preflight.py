from pathlib import Path

from cs_caller.preflight import (
    check_ndi_backend_module_available,
    check_ndi_runtime_available,
    collect_preflight_report,
)


def test_check_ndi_runtime_available_detects_by_library() -> None:
    ok, detail = check_ndi_runtime_available(
        find_library=lambda name: "libndi.so" if name == "ndi" else None,
        path_exists=lambda _: False,
        env={},
    )
    assert ok is True
    assert "NDI" in detail


def test_collect_preflight_report_ndi_runtime_missing() -> None:
    report = collect_preflight_report(
        mode="ndi",
        source_text="ndi://OBS",
        ndi_module_checker=lambda: (True, "模块已安装"),
        ndi_runtime_checker=lambda: (False, "未检测到 NDI Runtime"),
    )

    assert report.has_blocking_error is True
    assert any(item.key == "ndi_runtime" and (not item.ok) for item in report.items)
    assert "未检测到 NDI Runtime" in "\n".join(report.hints)


def test_collect_preflight_report_ndi_backend_missing_is_blocking() -> None:
    report = collect_preflight_report(
        mode="ndi",
        source_text="ndi://OBS",
        ndi_module_checker=lambda: (False, "未安装 cyndilib"),
        ndi_runtime_checker=lambda: (True, "runtime ok"),
    )

    assert report.has_blocking_error is True
    item = next(it for it in report.items if it.key == "ndi_backend_module")
    assert item.ok is False
    assert "cyndilib" in item.detail


def test_check_ndi_backend_module_available_missing() -> None:
    ok, detail = check_ndi_backend_module_available(
        import_module=lambda _: (_ for _ in ()).throw(ImportError())
    )
    assert ok is False
    assert "cyndilib" in detail


def test_collect_preflight_report_capture_negative_index_is_blocking() -> None:
    report = collect_preflight_report(mode="capture", source_text="-1")

    assert report.has_blocking_error is True
    item = next(it for it in report.items if it.key == "capture_index_valid")
    assert item.ok is False
    assert ">= 0" in item.detail


def test_collect_preflight_report_mock_missing_file() -> None:
    report = collect_preflight_report(
        mode="mock",
        source_text="/tmp/not-exists.png",
        path_exists=lambda _: False,
    )

    assert report.has_blocking_error is True
    item = next(it for it in report.items if it.key == "mock_path_exists")
    assert item.ok is False


def test_collect_preflight_report_mock_file_exists() -> None:
    report = collect_preflight_report(
        mode="mock",
        source_text=str(Path("/tmp/ok.png")),
        path_exists=lambda _: True,
    )

    assert report.has_blocking_error is False


def test_collect_preflight_report_ndi_source_format_empty_after_scheme() -> None:
    report = collect_preflight_report(
        mode="ndi",
        source_text="ndi://   ",
        ndi_module_checker=lambda: (True, "ok"),
        ndi_runtime_checker=lambda: (True, "ok"),
    )

    item = next(it for it in report.items if it.key == "ndi_source_format")
    assert item.ok is False
    assert item.blocking is False
