from cs_caller.announcer import Announcer
from cs_caller.tts.base import BaseTTS


class FakeTTS(BaseTTS):
    def __init__(self) -> None:
        self.messages: list[str] = []

    def say(self, text: str) -> None:
        self.messages.append(text)


def test_announcer_respects_stability_and_cooldown() -> None:
    tts = FakeTTS()
    announcer = Announcer(tts=tts, cooldown_sec=2.0, stable_frames=2)

    assert announcer.process("Mid", now=0.0) is None
    assert announcer.process("Mid", now=0.1) == "敌人可能在 Mid"
    assert announcer.process("Mid", now=0.2) is None
    assert announcer.process("Mid", now=2.2) == "敌人可能在 Mid"

    assert len(tts.messages) == 2
