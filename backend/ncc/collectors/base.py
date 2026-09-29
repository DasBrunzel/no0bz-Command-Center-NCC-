from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(slots=True)
class Capabilities:
    provider: str
    available: bool
    metrics: list[str] = field(default_factory=list)
    reason: str | None = None
    hint: str | None = None


class SensorProvider(ABC):
    name: ClassVar[str]
    platforms: ClassVar[set[str]] = {"any"}
    priority: ClassVar[int] = 10
    interval: ClassVar[float] = 1.0

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def probe(self) -> Capabilities: ...

    @abstractmethod
    def collect(self) -> dict[str, Any]: ...

