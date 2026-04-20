# cli2slivka/parsers/registry.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, Type, Optional

from cli2slivka.parsers.base import CLIParser


def register_parser(cls):
    ParserRegistry.register(cls)
    return cls

class ParserRegistry:
    """
    Central registry for CLI parsers.

    Supports:
    - explicit format lookup
    - automatic parser selection by file extension
    - optional content sniffing
    """

    _parsers_by_format: Dict[str, Type[CLIParser]] = {}
    _parsers: Dict[str, Type[CLIParser]] = {}

    # ------------------------------------------------------------------ #
    # Registration API
    # ------------------------------------------------------------------ #

    @classmethod
    def register(cls, parser_cls: Type[CLIParser]) -> None:
        """
        Register a parser class.
        """
        if not issubclass(parser_cls, CLIParser):
            raise TypeError(
                f"{parser_cls.__name__} must extend CLIParser"
            )

        cls._parsers[parser_cls.__name__] = parser_cls

        for fmt in getattr(parser_cls, "formats", []):
            if fmt in cls._parsers_by_format:
                raise ValueError(
                    f"Parser already registered for format '{fmt}'"
                )
            cls._parsers_by_format[fmt] = parser_cls

    # ------------------------------------------------------------------ #
    # Lookup API
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_format(cls, fmt: str) -> CLIParser:
        """
        Get a parser instance by explicit format name.
        """
        try:
            parser_cls = cls._parsers_by_format[fmt]
        except KeyError as exc:
            raise KeyError(
                f"No parser registered for format '{fmt}'"
            ) from exc

        return parser_cls()

    @classmethod
    def detect(cls, path: str | Path) -> CLIParser:
        """
        Automatically detect the correct parser for a given file.
        """
        path = Path(path)
        suffix = path.suffix.lower()

        # 1. Try suffix-based detection
        for parser_cls in cls._parsers.values():
            for sfx in getattr(parser_cls, "suffixes", []):
                if suffix == sfx:
                    return parser_cls()

        # 2. Try content-based sniffing
        for parser_cls in cls._parsers.values():
            if parser_cls.can_parse(path):
                return parser_cls()

        raise ValueError(
            f"Could not detect parser for file: {path}"
        )

    @classmethod
    def available_formats(cls):
        """
        Return all supported format names.
        """
        return sorted(cls._parsers_by_format.keys())

        

