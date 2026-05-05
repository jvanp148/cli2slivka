# cli2slivka/parsers/registry.py

from __future__ import annotations

from pathlib import Path
from typing import Dict, Type

from cli2slivka.parsers.base import CLIParser

"""
Handles how parsers are registered, found, and selected at runtime.
-> tells which parser to use for a certain format
-> figures out which parser to use for a file
"""

# Decorator => when you do @register_parser above a f.e. class GalaxyParser(); then that
# parser will automatically be registered. 

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

    # dictionaries that store the format name -> parser class and class name -> parser class
    _parsers_by_format: Dict[str, Type[CLIParser]] = {}
    _parsers: Dict[str, Type[CLIParser]] = {}

    # ------------------------------------------------------------------ #
    # Registration API
    # ------------------------------------------------------------------ #

    @classmethod # cls is here the same as self!
    def register(cls, parser_cls: Type[CLIParser]) -> None:
        """Register a parser class. The class must be a subclass of CLIParser and declare supported formats.
        Parsers are registered by their class name and by their supported format names.

        Args:
            parser_cls: Parser class to register.

        Raises:
            TypeError: If parser_cls does not subclass CLIParser.
            ValueError: If a parser is already registered for one of its formats.
        """
        if not issubclass(parser_cls, CLIParser):
            raise TypeError(f"{parser_cls.__name__} must extend CLIParser") # must inherit from CLIParser,
            # because every parser must follow the rules defined in CLIParser! If not, then TypeError!

        cls._parsers[parser_cls.__name__] = parser_cls # store by class name f.e. cls._parsers["GalaxyParser"] = GalaxyParser

        for fmt in getattr(parser_cls, "formats", []):  # register its supported formats, when not existing then empty list
            if fmt in cls._parsers_by_format:
                raise ValueError(
                    f"Parser already registered for format '{fmt}'"
                )
            cls._parsers_by_format[fmt] = parser_cls # f.e.  "galaxy": GalaxyParser

    # ------------------------------------------------------------------ #
    # Lookup API                                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_format(cls, fmt: str) -> CLIParser:
        """Get a parser instance by explicit format name.

        Args:
            fmt: Registered parser format name.

        Returns:
            An instance of the registered parser.

        Raises:
            KeyError: If no parser is registered for the given format.
        """
        try:
            parser_cls = cls._parsers_by_format[fmt] # for "galaxy" it gives GalaxyParser
        except KeyError as exc:
            raise KeyError(
                f"No parser registered for format '{fmt}'"
            ) from exc

        return parser_cls()

    @classmethod
    def detect(cls, path: str | Path) -> CLIParser:
        """Automatically detect the correct parser for a given file.

        Args:
            path: Path to the candidate file.

        Returns:
            An instance of the detected parser.

        Raises:
            ValueError: If no parser can be detected for the given path.
        """
        path = Path(path)
        suffix = path.suffix.lower()

        # 1. Try suffix-based detection
        for parser_cls in cls._parsers.values(): # parsers inherits suffixes from CLIParser
            for sfx in getattr(parser_cls, "suffixes", []):
                if suffix == sfx:
                    return parser_cls() # if it is the suffix, then return the class because it is that one.

        # 2. Try content-based sniffing -> if it starts with <tool> tag -> can parse!
        for parser_cls in cls._parsers.values():
            if parser_cls.can_parse(path):
                return parser_cls()

        raise ValueError(
            f"Could not detect parser for file: {path}"
        )

    @classmethod
    def available_formats(cls):
        """Return all supported parser format names.

        Returns:
            A sorted list of supported format names.
        """
        return sorted(cls._parsers_by_format.keys())

        

