from cs_caller.timeout_settings import (
    DEFAULT_GUI_CONNECT_TIMEOUT_MS,
    read_gui_connect_timeout_ms,
)


def test_read_gui_connect_timeout_ms_returns_default_when_env_missing() -> None:
    assert read_gui_connect_timeout_ms({}) == DEFAULT_GUI_CONNECT_TIMEOUT_MS


def test_read_gui_connect_timeout_ms_accepts_value_in_valid_range() -> None:
    assert read_gui_connect_timeout_ms({"CS_CALLER_CONNECT_TIMEOUT_MS": "3000"}) == 3000
    assert read_gui_connect_timeout_ms({"CS_CALLER_CONNECT_TIMEOUT_MS": "10000"}) == 10000
    assert read_gui_connect_timeout_ms({"CS_CALLER_CONNECT_TIMEOUT_MS": "30000"}) == 30000


def test_read_gui_connect_timeout_ms_rejects_out_of_range_or_invalid_values() -> None:
    invalid_inputs = ["2999", "30001", "abc", "10.5", "", "   "]
    for raw in invalid_inputs:
        assert (
            read_gui_connect_timeout_ms({"CS_CALLER_CONNECT_TIMEOUT_MS": raw})
            == DEFAULT_GUI_CONNECT_TIMEOUT_MS
        )
