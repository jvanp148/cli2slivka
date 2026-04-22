### Canonical CLI model (ICM = intermediate cli model) 
# SlivkaService and parameter classes = all properties that are needed to write the yaml.
# Canonical model = A canonical model is a design pattern used to communicate between different data formats. 

"""
This code defines a canonical internal model for describing a command‑line tool so that it can later be:
    - parsed from a Galaxy XML tool definition
    - represented in Python as a structured object
    - serialized into a Slivka YAML service description

It is essentially a schema for describing:
    1. Parameters (inputs the tool accepts)
    2. Arguments (how parameters map to CLI flags)
    3. Outputs (files the tool produces)
    4. The service itself (metadata + parameters + args + outputs)
"""

from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# ===========================================================================
# Parameter classes
# ===========================================================================
"""
Describes the base class for every parameter type.
1. File
2. Text
3. Integer
4. Decimal
5. Flag
6. Choice
"""

class SlivkaParameter(ABC):
    """
    Abstract base for all Slivka parameter types.
    Each parameter has a slug (internal identifier), a name, galaxy_name, 
    descr, required or not and default properties. 
    """

    def __init__(
        self,
        slug: str,
        name: str,
        *,
        galaxy_name: str = "",  #%# soap_name:
        description: str = "",
        required: bool = True,
        default=None,
    ):
        self.slug        = slug
        self.name        = name
        self.galaxy_name = galaxy_name or slug
        self.description = description
        self.required    = required
        self.default     = default

    @property
    @abstractmethod
    def slivka_type(self) -> str:
        """The Slivka type string written to YAML."""

    def extra_fields(self) -> dict:
        """Subclasses override this to add type-specific YAML fields."""
        return {}

    def to_dict(self) -> dict:
        """Builds the final dictionary that will appear in the YAML."""
        d: dict = {
            "name":     self.name,
            "type":     self.slivka_type,
            "required": self.required,
        }
        if self.description:
            d["description"] = self.description
        if self.default is not None:   
            d["default"] = self.default  
        d.update(self.extra_fields())
        return d

# each subclass inherits the SlivkaParameter class. 
class FileParameter(SlivkaParameter):
    slivka_type = "file"
# Adding media_type           
    def __init__(self, *args, media_type: str = "", symlink_name: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.media_type = media_type
        self.symlink_name = symlink_name
    # Placing extra properties in the parameter by adding to the dict.
    def extra_fields(self) -> dict:
        extra_field_dict = {}
        if self.symlink_name:
            extra_field_dict["symlink_name"] = self.symlink_name
        if self.media_type:
            extra_field_dict["media_type"] = self.media_type
        return extra_field_dict


class TextParameter(SlivkaParameter):
    slivka_type = "text"
# Adding max_length
    def __init__(self, *args, max_length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def extra_fields(self) -> dict:
        if self.max_length is not None:
            return {"max-length": self.max_length}
        return {}


class IntegerParameter(SlivkaParameter):
    slivka_type = "integer"
# Adding min and max_val being integers
    def __init__(self, *args, min_val: int | None = None, max_val: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_val = min_val
        self.max_val = max_val

    def extra_fields(self) -> dict:
        d = {}
        if self.min_val is not None:
            d["min"] = self.min_val
        if self.max_val is not None:
            d["max"] = self.max_val
        return d


class DecimalParameter(SlivkaParameter):
    slivka_type = "decimal"
# Adding min and max_val being floats
    def __init__(self, *args, min_val: float | None = None, max_val: float | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_val = min_val
        self.max_val = max_val

    def extra_fields(self) -> dict:
        d = {}
        if self.min_val is not None:
            d["min"] = self.min_val
        if self.max_val is not None:
            d["max"] = self.max_val
        return d


class FlagParameter(SlivkaParameter):
    slivka_type = "flag"
# No extra properties, but required is automatically set on False.
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)


class ChoiceParameter(SlivkaParameter):
    slivka_type = "choice"

    def __init__(self, *args, choices: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices: dict = choices or {}

    def extra_fields(self) -> dict:
        if self.choices:
            return {"choices": self.choices}
        return {}


# ===========================================================================
# Arg and Output
# ===========================================================================
# This class describes how a parameter becomes a CLI argument.

@dataclass # with dataclass, no def __init__() is needed. Just directly the 
# different properties, 
class SlivkaArg:
    """Maps one parameter to its command-line argument string."""
    slug:    str # which parameter this arg refers to
    arg:     str # the cli flag
    symlink: str | None = None # create symlink before running # if not in there than None
    join:    str | None = None # join list values with delimiter    
    default: str | None = None   # e.g. "present" for constant args

    def to_dict(self) -> dict:
        d: dict = {"arg": self.arg}
        if self.symlink is not None: d["symlink"] = self.symlink
        if self.join    is not None: d["join"]    = self.join   
        if self.default is not None: d["default"] = self.default
        return d


# One output file definition
@dataclass
class SlivkaOutput:
    """Describes one output file produced by the tool."""
    name:       str
    path:       str
    media_type: str
    label:      str = ""    

    def to_dict(self) -> dict:
        return {
            "name":       self.label or self.name,
            "path":       self.path,
            "media-type": self.media_type,
        }


# ===========================================================================
# SlivkaService  -  the central object
# ===========================================================================
"""
This is the complete representation of a Slivka service.

It contains:
    metadata (name, description, version, license, etc.)
    parameters — list of SlivkaParameter objects
    args — list of SlivkaArg objects
    outputs — list of SlivkaOutput objects
    command — the actual CLI command template
    slivka_version — version of the Slivka spec

It also provides helper methods: add_parameter(), add-arg(), add_output(), get_parameter(slug)
"""

@dataclass
class SlivkaService:
    """
    Holds the complete description of a Slivka service.
    Constructed by GalaxyXMLParser; serialised by SlivkaYAMLWriter.
    """
    name:           str
    description:    str
    version:        str
    author:         str              = "EMBOSS"
    license:        str              = "GPL"
    classifiers:    list             = field(default_factory=list)
    parameters:     list             = field(default_factory=list)
    args:           list             = field(default_factory=list)
    outputs:        list             = field(default_factory=list)
    command:        str              = ""
    slivka_version: str              = "0.8.3"
    
    def add_parameter(self, param: SlivkaParameter) -> "SlivkaService":
        self.parameters.append(param)
        return self

    def add_arg(self, arg: SlivkaArg) -> "SlivkaService":
        self.args.append(arg)
        return self

    def add_output(self, output: SlivkaOutput) -> "SlivkaService":
        self.outputs.append(output)
        return self

    def get_parameter(self, slug: str) -> SlivkaParameter | None:
        return next((p for p in self.parameters if p.slug == slug), None)