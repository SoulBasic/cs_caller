"""应用设置持久化。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

SUPPORTED_SOURCE_MODES = {"mock", "ndi", "capture"}
SUPPORTED_TTS_BACKENDS = {"auto", "pyttsx3", "console"}


@dataclass
class AppSettings:
    """GUI 运行时可持久化设置。"""

    map_name: str = "de_dust2"
    source_mode: str = "mock"
    source: str = ""
    tts_backend: str = "auto"


class AppSettingsStore:
    """读取/写入 app_settings.yaml。"""

    def __init__(self, settings_path: str | Path = "config/app_settings.yaml") -> None:
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppSettings:
        if not self.settings_path.exists():
            return AppSettings()

        with self.settings_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        map_name = str(data.get("map_name") or AppSettings.map_name).strip() or AppSettings.map_name
        source_mode = _normalize_source_mode(data.get("source_mode"))
        source = str(data.get("source") or "").strip()
        tts_backend = _normalize_tts_backend(data.get("tts_backend"))
        return AppSettings(
            map_name=map_name,
            source_mode=source_mode,
            source=source,
            tts_backend=tts_backend,
        )

    def save(self, settings: AppSettings) -> Path:
        payload = asdict(
            AppSettings(
                map_name=settings.map_name.strip() or AppSettings.map_name,
                source_mode=_normalize_source_mode(settings.source_mode),
                source=settings.source.strip(),
                tts_backend=_normalize_tts_backend(settings.tts_backend),
            )
        )
        with self.settings_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
        return self.settings_path


def _normalize_source_mode(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_SOURCE_MODES:
        return normalized
    return AppSettings.source_mode


def _normalize_tts_backend(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_TTS_BACKENDS:
        return normalized
    return AppSettings.tts_backend

