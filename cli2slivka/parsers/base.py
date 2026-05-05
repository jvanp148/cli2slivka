# parsers/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from cli2slivka.model.canonical import SlivkaService

"""
This file is basically defining a common interface (a contract) for all “parsers” in your project. 
It doesn't do parsing itself—it forces other classes to follow a consistent structure.
"""

# All parsers must:
#
# Implement .parse(path) → CanonicalCLI
# Declare:
#
# supported format names
# recognizable file suffixes and/or sniffing rules

class CLIParser(ABC):
    #: short symbolic names (e.g. "galaxy", "acd")
    formats: Iterable[str] = ()   # in the galaxy.py formats are specified as formats = ('galaxy', 'galaxy-xml', 'xml')

    #: file suffixes this parser understands
    suffixes: Iterable[str] = () # in the galaxy.py suffixes are specified as suffixes = ('.xml',)


    @abstractmethod
    def parse(self, path: str | Path) -> SlivkaService:
        """Parse the given CLI definition file into a SlivkaService.

        Args:
            path: Path to the source tool definition file.

        Returns:
            A fully populated SlivkaService instance.
        """
        pass

    @classmethod
    def can_parse(cls, path: str | Path) -> bool:
        """Determine whether this parser can parse the given file.

        Args:
            path: Path to the candidate file.

        Returns:
            True if the parser recognizes the file format; False otherwise.
        """
        return False

    # ------------------------------------------------------------------
    # Hook: override in subclasses
    # ------------------------------------------------------------------
    def post_process(self, service: SlivkaService) -> None:
        """Perform any post-processing on a parsed SlivkaService.

        Args:
            service: The SlivkaService to adjust after parsing.
        """
        pass