import time

from cs_caller.ndi_handshake import parse_ndi_probe_payload, run_ndi_probe_in_subprocess


def _sleep_worker(_: str, __: int, ___: object) -> None:
    time.sleep(5.0)


def test_run_ndi_probe_in_subprocess_terminates_worker_on_timeout() -> None:
    result = run_ndi_probe_in_subprocess(
        "OBS",
        timeout_s=0.3,
        worker_target=_sleep_worker,
    )
    assert result.ok is False
    assert result.timed_out is True
    assert result.worker_terminated is True
    assert "超时" in result.format_error()


def test_parse_ndi_probe_payload_prefers_explicit_count_and_names() -> None:
    result = parse_ndi_probe_payload(
        {
            "ok": False,
            "error": "boom",
            "discovered_names": ["OBS", " ", "DeskCam"],
            "discovered_count": 2,
            "selected_name": "OBS",
        }
    )
    assert result.ok is False
    assert result.error == "boom"
    assert result.discovered_names == ("OBS", "DeskCam")
    assert result.discovered_count == 2
    assert result.selected_name == "OBS"
