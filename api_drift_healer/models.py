from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedRequest:
    """Format-independent API request used by the core drift engine."""

    name: str
    method: str
    path: str
    body: dict[str, Any]

    def __post_init__(self) -> None:
        name = self.name.strip()
        method = self.method.strip().upper()
        path = self.path.strip()

        if not name:
            raise ValueError("Request name cannot be empty.")

        if not method:
            raise ValueError("Request method cannot be empty.")

        if not path:
            raise ValueError("Request path cannot be empty.")

        if not isinstance(self.body, dict):
            raise TypeError("Request body must be a dictionary.")

        if not path.startswith("/"):
            path = f"/{path}"

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "body", dict(self.body))
