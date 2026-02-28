from pathlib import Path

from cs_caller.app_settings import AppSettings, AppSettingsStore


def test_app_settings_load_defaults_when_file_missing(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app_settings.yaml"
    loaded = AppSettingsStore(path).load()
    assert loaded == AppSettings()


def test_app_settings_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app_settings.yaml"
    store = AppSettingsStore(path)
    settings = AppSettings(
        map_name="de_inferno",
        source_mode="ndi",
        source="ndi://OBS",
        tts_backend="pyttsx3",
        detect_enabled=True,
    )

    saved_path = store.save(settings)
    assert saved_path == path
    assert path.exists()

    loaded = store.load()
    assert loaded.map_name == "de_inferno"
    assert loaded.source_mode == "ndi"
    assert loaded.source == "ndi://OBS"
    assert loaded.tts_backend == "pyttsx3"
    assert loaded.detect_enabled is True


def test_app_settings_invalid_values_fallback_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app_settings.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "map_name: de_mirage\nsource_mode: bad_mode\nsource: abc\ntts_backend: bad_tts\ndetect_enabled: maybe\n",
        encoding="utf-8",
    )

    loaded = AppSettingsStore(path).load()
    assert loaded.map_name == "de_mirage"
    assert loaded.source_mode == "mock"
    assert loaded.source == "abc"
    assert loaded.tts_backend == "auto"
    assert loaded.detect_enabled is False


def test_app_settings_save_normalizes_values(tmp_path: Path) -> None:
    path = tmp_path / "config" / "app_settings.yaml"
    store = AppSettingsStore(path)
    store.save(
        AppSettings(
            map_name="  ",
            source_mode="NDI",
            source="  ndi://OBS  ",
            tts_backend="CONSOLE",
            detect_enabled=1,
        )
    )
    loaded = store.load()
    assert loaded.map_name == "de_dust2"
    assert loaded.source_mode == "ndi"
    assert loaded.source == "ndi://OBS"
    assert loaded.tts_backend == "console"
    assert loaded.detect_enabled is True
