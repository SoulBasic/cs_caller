"""NDI 握手探测：通过短生命周期子进程隔离潜在阻塞。"""

from __future__ import annotations

import multiprocessing
from multiprocessing.context import BaseContext
from queue import Empty
import sys
from dataclasses import dataclass
from typing import Any


DEFAULT_NDI_PROBE_TIMEOUT_S = 3.0
DEFAULT_NDI_CONNECT_TIMEOUT_MS = 1500


@dataclass(frozen=True)
class NDIProbeResult:
    ok: bool
    error: str | None
    selected_name: str
    discovered_names: tuple[str, ...]
    discovered_count: int
    timed_out: bool = False
    worker_terminated: bool = False

    def format_error(self) -> str:
        if self.error:
            return self.error
        return "NDI 握手失败"


def parse_ndi_probe_payload(payload: Any) -> NDIProbeResult:
    """把 worker 结果标准化，保证主进程错误展示稳定。"""

    data = payload if isinstance(payload, dict) else {}
    names_raw = data.get("discovered_names")
    names: list[str] = []
    if isinstance(names_raw, (list, tuple)):
        for item in names_raw:
            text = str(item).strip()
            if text:
                names.append(text)

    discovered_count = int(data.get("discovered_count") or len(names))
    selected_name = str(data.get("selected_name") or "").strip()
    error = data.get("error")
    error_text = str(error).strip() if error is not None else None

    return NDIProbeResult(
        ok=bool(data.get("ok")),
        error=error_text or None,
        selected_name=selected_name,
        discovered_names=tuple(names),
        discovered_count=max(0, discovered_count),
    )


def _ndi_probe_worker(
    source_text: str,
    connect_timeout_ms: int,
    result_queue: multiprocessing.Queue,
) -> None:
    from cs_caller.sources.ndi_native import probe_ndi_handshake

    try:
        probe = probe_ndi_handshake(source_text, connect_timeout_ms=connect_timeout_ms)
        names = [item.name for item in probe.discovered if item.name]
        result_queue.put(
            {
                "ok": True,
                "selected_name": probe.selected.name,
                "discovered_names": names,
                "discovered_count": len(names),
            }
        )
    except Exception as exc:
        result_queue.put(
            {
                "ok": False,
                "error": str(exc),
            }
        )


def _resolve_mp_context() -> BaseContext:
    if sys.platform.startswith("win"):
        return multiprocessing.get_context("spawn")
    return multiprocessing.get_context()


def run_ndi_probe_in_subprocess(
    source_text: str,
    *,
    timeout_s: float = DEFAULT_NDI_PROBE_TIMEOUT_S,
    connect_timeout_ms: int = DEFAULT_NDI_CONNECT_TIMEOUT_MS,
    mp_context: BaseContext | None = None,
    worker_target: Any | None = None,
) -> NDIProbeResult:
    """在 helper process 内执行 discover/connect 探测并带硬超时兜底。"""

    ctx = mp_context or _resolve_mp_context()
    queue_obj = ctx.Queue(maxsize=1)
    target = worker_target or _ndi_probe_worker
    process = ctx.Process(
        target=target,
        args=(source_text, int(connect_timeout_ms), queue_obj),
        daemon=True,
    )
    process.start()
    process.join(timeout=max(0.1, float(timeout_s)))

    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(timeout=1.0)
        return NDIProbeResult(
            ok=False,
            error=f"NDI 握手超时（>{timeout_s:.1f}s），已终止子进程，请重试",
            selected_name="",
            discovered_names=(),
            discovered_count=0,
            timed_out=True,
            worker_terminated=True,
        )

    payload: Any
    try:
        payload = queue_obj.get_nowait()
    except Empty:
        payload = {
            "ok": False,
            "error": f"NDI 握手子进程异常退出（exit={process.exitcode}）",
        }
    return parse_ndi_probe_payload(payload)
