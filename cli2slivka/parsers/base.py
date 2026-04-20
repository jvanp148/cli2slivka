# parsers/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from cli2slivka.model.canonical import SlivkaService

# All parsers must:
#
# Implement .parse(path) → CanonicalCLI
# Declare:
#
# supported format names
# recognizable file suffixes and/or sniffing rules

class CLIParser(ABC):
    #: short symbolic names (e.g. "galaxy", "acd")
    formats: Iterable[str] = ()

    #: file suffixes this parser understands
    suffixes: Iterable[str] = ()

    @abstractmethod
    def parse(self, path: str | Path) -> SlivkaService:
        pass

    @classmethod
    def can_parse(cls, path: str | Path) -> bool:
        """
        Optional content-based sniffing.
        Override if needed.
        """
        return False

    # ------------------------------------------------------------------
    # Hook: override in subclasses
    # ------------------------------------------------------------------
    def post_process(self, service: SlivkaService) -> None:
        """Called after the service is fully built. Override freely."""
        pass