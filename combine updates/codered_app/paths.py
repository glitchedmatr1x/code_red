from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT_MARKERS = (
    "main.py",
    "python_workbench.py",
    "Run_Code_RED.bat",
)


def find_repo_root(start: Path | None = None) -> Path:
    """Find the Code RED root without relying on the current working directory."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in ROOT_MARKERS):
            return candidate
    # Fallback for direct package use from the canonical layout.
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CodeRedPaths:
    root: Path

    @classmethod
    def detect(cls, start: Path | None = None) -> "CodeRedPaths":
        return cls(find_repo_root(start))

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def codered_data(self) -> Path:
        return self.data / "codered"

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def related_apps(self) -> Path:
        return self.root / "related_apps"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def research(self) -> Path:
        return self.root / "research"

    @property
    def scratch(self) -> Path:
        return self.root / "scratch"

    @property
    def tools(self) -> Path:
        return self.root / "tools"

    @property
    def imports(self) -> Path:
        return self.root / "imports"

    @property
    def game(self) -> Path:
        return self.root / "game"

    def ensure_runtime_dirs(self) -> None:
        for path in (self.imports, self.game, self.logs, self.reports, self.scratch):
            path.mkdir(parents=True, exist_ok=True)
