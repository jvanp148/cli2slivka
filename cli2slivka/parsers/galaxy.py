# ===========================================================================
# GalaxyXMLParser
# ===========================================================================

import re
from pathlib import Path
from xml.etree import ElementTree as ET  
from  cli2slivka.utils.xml import slugify, strip_macro_placeholders
from cli2slivka.model.canonical import SlivkaArg, SlivkaOutput, SlivkaParameter, SlivkaService, TextParameter, FileParameter, IntegerParameter, DecimalParameter, ChoiceParameter, FlagParameter
from cli2slivka.parsers.base import CLIParser
from cli2slivka.parsers.registry import register_parser


@register_parser # automatically registers parser method
class GalaxyXMLParser(CLIParser):
    """
    Reads a Galaxy XML tool wrapper and builds a SlivkaService.

    Extend this class and override post_process() to customise
    behaviour for specific tools without touching the base logic.

    Example
    -------
    class NeedleParser(GalaxyXMLParser):
        def post_process(self, service):
            # Force gapopen to have a max bound
            p = service.get_parameter("gapopen")
            if p:
                p.max_val = 100.0
    """

    #: short symbolic names (e.g. "galaxy", "acd")
    formats = ('galaxy', 'galaxy-xml', 'galaxy_xml')

    #: file suffixes this parser understands
    suffixes = ('.xml',) #%# will be problem when soap also has .xml!

### This could come into a separate file.
# Mapping galaxy parameters to slivka parameter classes 
    TYPE_MAP: dict = {
        "data":    FileParameter,
        "text":    TextParameter,
        "integer": IntegerParameter,
        "float":   DecimalParameter,
        "boolean": FlagParameter,
        "select":  ChoiceParameter,
    }

# Mapping galaxy output formats to mime types for slivka yaml
    FORMAT_MEDIA_MAP: dict = {
        "fasta":   "application/fasta",
        "clustal": "application/clustal",
        "phylip":  "application/phylip",
        "nhx":     "text/plain",
        "needle":  "text/plain",
        "txt":     "text/plain",
        "tabular": "text/tab-separated-values",
        "html":    "text/html",
        "pdf":     "application/pdf",
    }

# Mapping galaxy output formats to file extensions
    FORMAT_EXT_MAP: dict = {
        "fasta":   "fasta",
        "clustal": "aln",
        "phylip":  "phy",
        "nhx":     "dnd",
        "needle":  "needle",
    }

    # The constructor prepares storage for XML tree, root node and command string (allocates place 
    # in memory, but only later on can something take place, can also easily be replaced...)

    def __init__(self):
        self._tree    = None
        self._root    = None # root element is tool
        self._raw_cmd = "" # prepares the raw command, later filled with <command> text

    @classmethod # setting this function completely for the galaxy parser
    def can_parse(cls, path):
        try:    
            with open(path, "rb") as fh:
                line = fh.readline(1024)  # limit read size
                return b"<tool" in line
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    # Here you are doing the XML to Python object, and putting this in the SlivkaService to go to YAML.

    def parse(self, xml_path: str | Path) -> SlivkaService: # -> .. is typing, just saying what it will return
        # Creating an empty slivka service.
        # Loading the XML as a python object tree
        self.xml_path = xml_path
        self._tree    = ET.parse(xml_path)
        self._root    = self._tree.getroot() # root element is tool

        service = SlivkaService(
            name        = self._parse_name(), # taking name out of the xml and placing it in name
            description = self._parse_description(),
            version     = self._parse_version(),
            classifiers = self._parse_classifiers(),
            command     = self._parse_executable(),
        )
        # using previous defined fundtions to add params, args and outputs
        # to the slivkaservice
        params = self._parse_parameters()
        for p in params:
            service.add_parameter(p)

        for arg in self._build_args(params):
            service.add_arg(arg)

        for output in self._parse_outputs():
            service.add_output(output)

        service.add_output(SlivkaOutput(
            name="error-log", path="stderr",
            media_type="text/plain", label="Error Log",
        ))

        self.post_process(service)
        return service

    # ------------------------------------------------------------------
    # Hook: override in subclasses
    # ------------------------------------------------------------------

    def post_process(self, service: SlivkaService) -> None:
        """Called after the service is fully built. Override freely.
        If there still is something not right, you can here adapt it"""

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _parse_name(self) -> str:
        return self._root.get("name", Path(self.xml_path).stem)

    def _parse_description(self) -> str:
        el = self._root.find("description")
        return el.text.strip() if el is not None and el.text else ""

    def _parse_version(self) -> str:
        raw = self._root.get("version", "1.0")
        v   = strip_macro_placeholders(raw)
        return v or "1.0"

    def _parse_classifiers(self) -> list:
        classifiers = []
        for cit in self._root.findall(".//citation[@type='doi']"):
            if cit.text:
                classifiers.append(f"Citation :: DOI :: {cit.text.strip()}")
        return classifiers

    def _parse_executable(self) -> str:
        cmd_el = self._root.find("command")
        if cmd_el is None:
            return ""
        self._raw_cmd = (cmd_el.text or "").strip()
        tokens = self._raw_cmd.split()
        return tokens[0] if tokens else ""

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def _parse_parameters(self) -> list:
        params     = []
        seen_names = set()

        def walk(node: ET.Element) -> None:
            for child in node:
                if child.tag == "param":
                    gname = child.get("name", "")
                    if not gname or gname in seen_names:
                        continue
                    seen_names.add(gname)
                    p = self._build_parameter(child)
                    if p is not None:
                        params.append(p)
                elif child.tag in ("conditional", "section", "inputs", "when"): # other types of parameters?
                    walk(child)

        inputs_el = self._root.find("inputs")
        if inputs_el is not None:
            walk(inputs_el)
        return params

# ET is module that already is made to get out easily the different tags of an xml
# ET.Element.get ->  get(key, default=None)
# -> Returns the attribute (key) value, or default if the attribute was not found.

    def _build_parameter(self, el: ET.Element) -> SlivkaParameter | None:
        gtype    = el.get("type", "text")
        cls      = self.TYPE_MAP.get(gtype, TextParameter) # Format (fmt)
        gname    = el.get("name", "")
        label    = el.get("label", gname)
        help_    = el.get("help", "")
        value    = el.get("value")
        slug     = slugify(gname)
        optional = el.get("optional", "false").lower() == "true"
        required = not optional

        common = dict(
            slug        = slug, # ID
            name        = label,
            galaxy_name = gname,
            description = help_,
            required    = required,
        )

        if cls is FileParameter:
            fmt = el.get("format", "")
            return FileParameter(
                **common, # see dict above this, inheriting these params, but also media_type
                media_type=self.FORMAT_MEDIA_MAP.get(fmt, f"application/{fmt}"),
            )

        if cls is ChoiceParameter:
            choices: dict = {}
            default_val = None
            for opt in el.findall("option"):
                opt_text  = opt.text.strip() if opt.text else opt.get("value", "")
                opt_value = opt.get("value", opt_text)
                choices[slugify(opt_text)] = opt_value
                if opt.get("selected", "false").lower() == "true":
                    default_val = opt_value
            return ChoiceParameter(**common, choices=choices, default=default_val)

        if cls is FlagParameter:
            return FlagParameter(**common, required=False)

        if cls is IntegerParameter:
            mn = int(el.get("min")) if el.get("min") is not None else None
            mx = int(el.get("max")) if el.get("max") is not None else None
            dv = int(value) if value is not None else None
            return IntegerParameter(**common, min_val=mn, max_val=mx, default=dv)

        if cls is DecimalParameter:
            mn = float(el.get("min")) if el.get("min") is not None else None
            mx = float(el.get("max")) if el.get("max") is not None else None
            dv = float(value) if value is not None else None
            return DecimalParameter(**common, min_val=mn, max_val=mx, default=dv)

        return TextParameter(**common, default=value)

    # ------------------------------------------------------------------
    # Args
    # ------------------------------------------------------------------

    def _build_args(self, params: list) -> list:
        return [self._detect_arg(p) for p in params]

    def _detect_arg(self, param: SlivkaParameter) -> SlivkaArg:
        gname = param.galaxy_name

        pattern = re.compile( # matches 3 patterns
            r"(-[\w]+\s+['\"]?\$" + re.escape(gname) + r"['\"]?)" # -threshold $threshold
            r"|(-[\w]+=\$" + re.escape(gname) + r")" # -threshold=$threshold
            r"|(\$" + re.escape(gname) + r"\b)", # standalone
            re.IGNORECASE,
        )
        m = pattern.search(self._raw_cmd) # try to find pattern in the raw command

        if m:
            matched = m.group(0).strip()
            arg_str = re.sub(r"\$" + re.escape(gname), "$(value)", matched)
        else:
            if isinstance(param, FileParameter):
                arg_str = f"-{gname} $(value)"
            elif isinstance(param, FlagParameter):
                arg_str = f"-{gname.upper()}"
            elif isinstance(param, ChoiceParameter):
                arg_str = f"-{gname.upper()} $(value)"
            else:
                arg_str = f"-{gname} $(value)"

        # Only for files! create symbolic file name 
        symlink = f"{gname}.input" if isinstance(param, FileParameter) else None # input.input sis real uploaded file
        return SlivkaArg(slug=param.slug, arg=arg_str, symlink=symlink)

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def _parse_outputs(self) -> list:
        outputs    = []
        outputs_el = self._root.find("outputs")
        if outputs_el is None:
            return outputs

        for data_el in outputs_el.findall("data"):
            name    = data_el.get("name", "output")
            fmt     = data_el.get("format", "txt")
            from_wd = data_el.get("from_work_dir", "")
            raw_lbl = data_el.get("label", name)
            label   = re.sub(r"\$\{.*?\}", "", raw_lbl).strip(": ")
            media   = self.FORMAT_MEDIA_MAP.get(fmt, f"application/{fmt}")
            ext     = self.FORMAT_EXT_MAP.get(fmt, "txt")
            path    = from_wd if from_wd else f"output.{ext}"

            outputs.append(SlivkaOutput(
                name=name, path=path, media_type=media, label=label or name,
            ))

        return outputs

