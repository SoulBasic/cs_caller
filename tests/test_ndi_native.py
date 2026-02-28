from cs_caller.sources.ndi_native import NDISourceInfo, normalize_requested_source_text, select_best_ndi_source


def _src(name: str) -> NDISourceInfo:
    return NDISourceInfo(name=name, address="", raw={"name": name})


def test_normalize_requested_source_text_accepts_plain_and_scheme() -> None:
    assert normalize_requested_source_text("OBS") == "OBS"
    assert normalize_requested_source_text(" ndi://OBS ") == "OBS"
    assert normalize_requested_source_text("  ndi://  OBS Studio  ") == "OBS Studio"


def test_select_best_ndi_source_prefers_exact_case_insensitive() -> None:
    discovered = [_src("OBS Studio (DESKTOP-1)"), _src("OBS")]
    selected = select_best_ndi_source("ndi://obs", discovered)
    assert selected is not None
    assert selected.name == "OBS"


def test_select_best_ndi_source_supports_contains_match() -> None:
    discovered = [_src("Gaming-PC (OBS)"), _src("Stream Camera")]
    selected = select_best_ndi_source("obs", discovered)
    assert selected is not None
    assert selected.name == "Gaming-PC (OBS)"


def test_select_best_ndi_source_returns_none_when_not_found() -> None:
    discovered = [_src("Room-A"), _src("Room-B")]
    assert select_best_ndi_source("OBS", discovered) is None
