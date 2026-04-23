# ===========================================================================
# SoapXMLParser
# ===========================================================================

import re
from pathlib import Path
from xml.etree import ElementTree as ET  
from  cli2slivka.utils.xml import slugify
from cli2slivka.model.canonical import SlivkaArg, SlivkaOutput, SlivkaService, TextParameter, FileParameter, IntegerParameter, DecimalParameter, ChoiceParameter
from cli2slivka.parsers.base import CLIParser
from cli2slivka.parsers.registry import register_parser

@register_parser
class SoapXMLParser(CLIParser):
    """
    Reads a Soaplab2 SOAP XML (DsLSRAnalysis) file and builds a SlivkaService.

    Extend this class and override post_process() to customise behaviour for
    specific tools without modifying the base logic.

    Example
    -------
    class NeedleParser(SoapXMLParser):
        def post_process(self, service):
            p = service.get_parameter("gapopen")
            if p:
                p.max_val = 100.0
    """
    formats = ('soap', 'soap-xml', 'soap_xml')
    suffixes = ('.xml',)
    
    # Maps SOAP type strings → SlivkaParameter subclass
    TYPE_MAP: dict = {
        "string":  None,          # resolved contextually (choice or text)
        "long":    IntegerParameter,
        "float":   DecimalParameter,
        "boolean": ChoiceParameter,
        "int":     IntegerParameter,
        "double":  DecimalParameter,
    }

    # EDAM URI prefix → human-readable Slivka classifier category
    EDAM_MAP: dict = {
        "EDAM_operation": "Operation",
        "EDAM_topic":     "Topic",
        "EDAM_data":      "Data",
        "EDAM_format":    "Format",
    }

    # Output extension by tool name (tool_name → extension used for outfile)
    OUTFILE_EXT_MAP: dict = {
        "needle":   "needle",
        "water":    "water",
        "stretcher":"stretcher",
        "matcher":  "matcher",
        "est2genome": "est2genome",
        "infoseq":  "infoseq",
        "seqret":   "fasta",
        "transeq":  "fasta",
        "pepstats": "pepstats",
        "pepinfo":  "pepinfo",
        "pepwindow":"pepwindow",
        "charge":   "charge",
        "iep":      "iep",
        "mwcontam": "mwcontam",
        "twofeat":  "twofeat",
        "showfeat": "showfeat",
        "showseq":  "showseq",
        "sixpack":  "sixpack",
        "getorf":   "fasta",
        "tcode":    "tcode",
        "cpgplot":  "cpgplot",
        "cpgreport":"cpgreport",
        "isochore": "isochore",
        "newcpgreport": "newcpgreport",
        "newcpgseek":   "newcpgseek",
    }

    # Output media-type by extension
    MEDIA_TYPE_MAP: dict = {
        "needle":   "text/plain",
        "water":    "text/plain",
        "fasta":    "application/fasta",
        "infoseq":  "text/plain",
        "txt":      "text/plain",
        "html":     "text/html",
        "pepstats": "text/plain",
        "pepinfo":  "text/plain",
    }
    def __init__(self):
        self._tree    = None
        self._root    = None # root element is tool
        self._analysis = None
        self._ext = None

    @classmethod # setting this function completely for the galaxy parser
    def can_parse(cls, path):
        try:    
            with open(path, "rb") as fh:
                line = fh.read(1024)  # limit read size
                return b"<analysis" in line
        except OSError:
            return False
    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def parse(self, xml_path: str | Path) -> SlivkaService:
        self.xml_path  = xml_path
        self._tree     = ET.parse(xml_path)
        self._root     = self._tree.getroot()
        # Top-level <analysis> element
        self._analysis = self._root.find("analysis")
        if self._analysis is None:
            raise ValueError("No <analysis> element found in SOAP XML.")
        # <analysis_extension> element (may be None for very simple files)
        self._ext = self._analysis.find("analysis_extension")

        service = SlivkaService(
            name        = self._parse_name(),
            description = self._parse_description(),
            version     = self._parse_version(),
            command     = self._parse_executable(),
            classifiers = self._parse_classifiers(),
        )

        params = self._parse_parameters()
        params.append(ChoiceParameter(
                        slug        = "help",
                        name        = "help",
                        description = "Help documentation of the tool.",
                        required    = False,
                        choices     = {
                            "yes": "Y", "no": "N"
                        },
                    ))
        for p in params:
            service.add_parameter(p)
        service.file_params = [p for p in params if isinstance(p, FileParameter) and p.required]

        for arg in self._build_args(params, service.command):
            service.add_arg(arg)

        for output in self._build_outputs(service.command):
            service.add_output(output)

        self.post_process(service)
        return service

    # ------------------------------------------------------------------
    # Hook: override in subclasses
    # ------------------------------------------------------------------

    def post_process(self, service: SlivkaService) -> None:
        """Called after the service is fully built. Override freely."""

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def _parse_name(self) -> str:
        return self._analysis.get("name", Path(self.xml_path).stem)

    def _parse_description(self) -> str:
        el = self._analysis.find("description")
        return el.text.strip() if el is not None and el.text else ""

    def _parse_version(self) -> str:
        return self._analysis.get("version", "1.0")

    def _parse_executable(self) -> str:
        """Read the exe filename from <analysis_extension><event><action file="...">."""
        if self._ext is None:
            return self._parse_name()
        action = self._ext.find(".//action[@type='exe']")
        if action is not None:
            return action.get("file", self._parse_name())
        return self._parse_name()

    def _parse_classifiers(self) -> list:
        """
        Build classifiers from EDAM <option> tags in <analysis_extension>.
        Pattern:  <option name="EDAM_operation:0494" value="Pairwise sequence alignment...">
        Produces: 'Operation :: Pairwise sequence alignment (global)'
        """
        classifiers = []
        if self._ext is None:
            return classifiers

        # options that are direct children of <analysis_extension> (tool-level)
        for opt in self._ext.findall("option"):
            edam_name  = opt.get("name", "")
            edam_value = opt.get("value", "").replace("\n", " ").strip()
            edam_value = re.sub(r"\s+", " ", edam_value)
            for prefix, label in self.EDAM_MAP.items():
                if edam_name.startswith(prefix + ":"):
                    classifiers.append(f"{label} :: {edam_value}")
                    break
        return classifiers

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def _get_ext_param_map(self) -> dict:
        """
        Build a dict  soap_name → <base> element  from <analysis_extension>.
        This provides richer metadata (mandatory, prompt, help, range).
        """
        ext_map: dict = {}
        if self._ext is None:
            return ext_map
        for param_el in self._ext.findall("parameter"):
            base = param_el.find("base")
            if base is None:
                continue
            name = base.get("name", "")
            if name:
                ext_map[name] = (base, param_el)  # (base element, full parameter element)
        return ext_map

    def _parse_parameters(self) -> list:
        """
        Build the parameter list to match the Slivka YAML convention:

        1. Collect raw <input> elements from <analysis> for type/allowed info.
        2. Enrich with metadata (mandatory, prompt, help, range) from
           <analysis_extension><parameter> elements.
        3. Identify sequence file bases via SeqParameter server_class annotations.
        4. Build the final ordered list grouping each sequence file immediately
           with its qualifiers (sformat_, sbegin_, send_, sprotein_, snucleotide_,
           sreverse_, slower_, supper_) — matching the reference YAML layout.
        5. Skip output-only / companion fields:
           outfile, report, detailed_status, *_url, *_direct_data, *_usa
           (for non-file inputs the _direct_data / _url variants are skipped too).
        """
        ext_map = self._get_ext_param_map()

        # Collect all <input> elements in document order
        inputs    = self._analysis.findall("input")
        input_map: dict = {el.get("name", ""): el for el in inputs}

        # ---- Identify sequence file base names --------------------------------
        # Only promote to FileParameter when analysis_extension marks the parameter
        # with server_class containing "SeqParameter".  This excludes matrix-file
        # parameters (datafile) that share the _direct_data / _url naming pattern.
        file_bases: set = set()
        for sname, (base_el, _) in ext_map.items():
            srv_class = self._get_option_value(base_el, "server_class")
            if srv_class and "SeqParameter" in srv_class:
                file_bases.add(sname)

        # Fallback when analysis_extension carries no SeqParameter annotations
        if not file_bases:
            for name in input_map:
                if name.endswith("_direct_data"):
                    base = name[: -len("_direct_data")]
                    # Only if a corresponding _usa variant also exists
                    if base + "_usa" in input_map:
                        file_bases.add(base)

        # ---- Build the complete skip set ----------------------------------------
        # Names that should never appear as parameters
        SKIP_NAMES: set = {"outfile", "report", "detailed_status",
                           "outfile_url", "report_url", "detailed_status_url"}
        # Companion suffixes generated for every input (file or not)
        for base in file_bases:
            SKIP_NAMES |= {base + "_direct_data", base + "_usa", base + "_url"}
        # Also skip *_url / *_direct_data companions for non-file string inputs
        # e.g. datafile_direct_data, datafile_url
        for name in list(input_map):
            if name.endswith("_url") or name.endswith("_direct_data"):
                SKIP_NAMES.add(name)

        # ---- Build a rich ordering -------------------------------------------------
        # Strategy:  use the extension ordering as the primary sequence, then
        # inject each file-qualifier group right after its parent file parameter.

        SEQ_QUALIFIERS = ("sformat", "sbegin", "send", "sprotein",
                          "snucleotide", "sreverse", "slower", "supper")

        # Extension-declared names (their ordering is our authoritative order)
        ext_order: list = []
        if self._ext is not None:
            for param_el in self._ext.findall("parameter"):
                base = param_el.find("base")
                if base is not None:
                    n = base.get("name", "")
                    if n:
                        ext_order.append(n)

        # For each file base, collect its qualifier names that appear in input_map
        def qualifiers_for(file_base: str) -> list:
            result = []
            for q in SEQ_QUALIFIERS:
                candidate = f"{q}_{file_base}"
                if candidate in input_map:
                    result.append(candidate)
            return result

        # Build final order:
        # * Walk ext_order; when we see a file-base name, immediately append
        #   its qualifiers after it (those qualifiers are removed from their
        #   original position in ext_order / input_order).
        # * Anything in input_order not already covered is appended at the end
        #   (excluding skipped names).
        qualifier_set: set = set()
        for fb in file_bases:
            qualifier_set |= set(qualifiers_for(fb))

        order: list = []
        seen_order: set = set()

        for n in ext_order:
            if n in seen_order:
                continue
            seen_order.add(n)
            if n in qualifier_set:
                continue  # will be inserted right after the file-base
            order.append(n)
            if n in file_bases:
                for q in qualifiers_for(n):
                    if q not in seen_order:
                        seen_order.add(q)
                        order.append(q)

        # Append remaining input-order names (those absent from analysis_extension)
        input_order = [el.get("name", "") for el in inputs if el.get("name")]
        for n in input_order:
            if n in seen_order:
                continue
            seen_order.add(n)
            if n in qualifier_set:
                continue
            if n in SKIP_NAMES:
                continue
            order.append(n)
            if n in file_bases:
                for q in qualifiers_for(n):
                    if q not in seen_order:
                        seen_order.add(q)
                        order.append(q)

        # ---- Helper: get enriched metadata for a soap_name ----------------------
        def get_meta(soap_name: str) -> tuple:
            """Returns (mandatory: bool, description: str, base_el, param_el)."""
            if soap_name in ext_map:
                base_el, param_el = ext_map[soap_name]
                mandatory  = base_el.get("mandatory", "false").lower() == "true"
                prompt_el  = base_el.find("prompt")
                help_el    = base_el.find("help")
                prompt_text = ""
                help_text   = ""
                if prompt_el is not None and prompt_el.text:
                    prompt_text = re.sub(r"\s+", " ", prompt_el.text).strip().rstrip(".")
                if help_el is not None and help_el.text:
                    help_text = re.sub(r"\s+", " ", help_el.text).strip()
                if help_text and prompt_text:
                    if help_text.lower().startswith(prompt_text.lower()):
                        description = help_text
                    else:
                        description = f"{prompt_text}. {help_text}"
                else:
                    description = prompt_text or help_text
                return mandatory, description, base_el, param_el
            el = input_map.get(soap_name)
            if el is not None:
                mandatory = el.get("mandatory", "false").lower() == "true"
                return mandatory, "", None, None
            return False, "", None, None

        # ---- Build parameter objects --------------------------------------------
        params: list = []
        for soap_name in order:
            if soap_name in SKIP_NAMES:
                continue

            mandatory, description, base_el, param_el = get_meta(soap_name)
            slug = slugify(soap_name)

            # ---- Sequence file parameter ----------------------------------------
            if soap_name in file_bases:
                params.append(FileParameter(
                    slug         = slug,
                    name         = soap_name,
                    description  = description,
                    required     = mandatory,
                    symlink_name = f"{soap_name}.dat",
                ))
                continue

            # ---- All other parameters -------------------------------------------
            input_el = input_map.get(soap_name)
            raw_type = input_el.get("type", "string") if input_el is not None else "string"

            if raw_type == "boolean":
                params.append(ChoiceParameter(
                    slug        = slug,
                    name        = soap_name,
                    description = description,
                    required    = mandatory,
                    choices     = {"yes": "Y", "no": "N"},
                ))

            elif raw_type == "string":
                # Gather allowed values from flat <input> section
                allowed_vals: list = []
                if input_el is not None:
                    allowed_vals = [a.text.strip() for a in input_el.findall("allowed") if a.text]

                # Or from <list> inside analysis_extension parameter
                if not allowed_vals and base_el is not None and param_el is not None:
                    data_el = param_el.find("data")
                    if data_el is not None:
                        list_el = data_el.find("list")
                        if list_el is not None:
                            allowed_vals = [
                                li.get("value", "")
                                for li in list_el.findall("list_item")
                                if li.get("value")
                            ]

                if allowed_vals:
                    params.append(ChoiceParameter(
                        slug        = slug,
                        name        = soap_name,
                        description = description,
                        required    = mandatory,
                        choices     = {v: v for v in allowed_vals},
                    ))
                else:
                    params.append(TextParameter(
                        slug        = slug,
                        name        = soap_name,
                        description = description,
                        required    = mandatory,
                    ))

            elif raw_type in ("long", "int"):
                mn, mx = self._get_range(base_el, param_el, int)
                params.append(IntegerParameter(
                    slug        = slug,
                    name        = soap_name,
                    description = description,
                    required    = mandatory,
                    min_val     = mn,
                    max_val     = mx,
                ))

            elif raw_type in ("float", "double"):
                mn, mx = self._get_range(base_el, param_el, float)
                params.append(DecimalParameter(
                    slug        = slug,
                    name        = soap_name,
                    description = description,
                    required    = mandatory,
                    min_val     = mn,
                    max_val     = mx,
                ))
            # Unknown types: skip silently

        return params

    # ------------------------------------------------------------------
    # Range extraction helper
    # ------------------------------------------------------------------

    def _get_range(self, base_el, param_el, cast):
        """
        Extract (min, max) from:
          <option name="scalemin" value="0.0"> / <option name="scalemax" value="100.0">
        or from a <range min="0.0" max="100.0"> child of param_el.
        """
        mn = mx = None
        if base_el is not None:
            raw_min = self._get_option_value(base_el, "scalemin")
            raw_max = self._get_option_value(base_el, "scalemax")
            if raw_min is not None:
                try: mn = cast(raw_min)
                except ValueError: pass
            if raw_max is not None:
                try: mx = cast(raw_max)
                except ValueError: pass
        if param_el is not None and (mn is None or mx is None):
            range_el = param_el.find("range")
            if range_el is not None:
                rmin = range_el.get("min")
                rmax = range_el.get("max")
                if rmin is not None and mn is None:
                    try: mn = cast(rmin)
                    except ValueError: pass
                if rmax is not None and mx is None:
                    try: mx = cast(rmax)
                    except ValueError: pass
        return mn, mx

    @staticmethod
    def _get_option_value(base_el, option_name: str) -> str | None:
        """Find <option name="option_name" value="..."> inside a <base> element."""
        for opt in base_el.findall("option"):
            if opt.get("name") == option_name:
                return opt.get("value")
        return None

    # ------------------------------------------------------------------
    # Args
    # ------------------------------------------------------------------

    def _build_args(self, params: list, command: str) -> list:
        """
        Build the args list.

        Sequence qualifier suffix numbering:
          The EMBOSS convention uses -sformat1, -sbegin1 ... for the first
          sequence, -sformat2 ... for the second, etc.
          We detect sequence parameter groups by their soap_name suffix
          (_asequence, _bsequence, _sequence, ...) and assign seq_index
          automatically.
        """
        # Detect all sequence base names (parameters that are FileParameter)
        seq_bases: list = [p.name for p in params if isinstance(p, FileParameter)]

        # Map seq_base → index (1-based)
        seq_index: dict = {base: i + 1 for i, base in enumerate(seq_bases)}

        args: list = []
        for p in params:
            sname = p.name  # e.g. "sformat_asequence"

            if isinstance(p, FileParameter):
                # -asequence $(value)  with symlink
                arg_str = f"-{sname} $(value)"
                args.append(SlivkaArg(
                    slug    = p.slug,
                    arg     = arg_str,
                    symlink = p.symlink_name or f"{sname}.dat",
                ))
                continue

            # Check whether this param belongs to a sequence group
            # e.g. sformat_asequence → base "asequence", seq_num 1
            matched_base, seq_num = self._find_seq_group(sname, seq_bases, seq_index)

            # Determine qualifier (the EMBOSS flag name)
            # For sequence-modifiers (sformat, sbegin, send, sprotein, snucleotide,
            # sreverse, slower, supper) strip the _<base> suffix and add seq_num.
            SEQ_QUALIFIERS = ("sformat", "sbegin", "send", "sprotein",
                              "snucleotide", "sreverse", "slower", "supper")

            if matched_base is not None:
                # e.g. sformat_asequence → qualifier "sformat", num 1 → "-sformat1 $(value)"
                stripped = sname[: -(len(matched_base) + 1)]  # remove "_<base>"
                if stripped in SEQ_QUALIFIERS:
                    flag = f"-{stripped}{seq_num}"
                else:
                    flag = f"-{sname}"
            else:
                flag = f"-{sname}"

            arg_str = f"{flag} $(value)"
            args.append(SlivkaArg(slug=p.slug, arg=arg_str))

        # Append the _outfile arg (always last, with default filename)
        ext       = self.OUTFILE_EXT_MAP.get(command, "out")
        outfile   = f"outfile.{ext}"
        args.append(SlivkaArg(
            slug    = "_outfile",
            arg     = "-outfile $(value)",
            default = outfile,
        ))

        return args

    @staticmethod
    def _find_seq_group(sname: str, seq_bases: list, seq_index: dict):
        """
        Given a parameter name like 'sformat_asequence', find which
        seq_base ('asequence') it belongs to and its index.
        Returns (matched_base, seq_num) or (None, None).
        """
        for base in seq_bases:
            if sname.endswith("_" + base):
                return base, seq_index[base]
        return None, None

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------

    def _build_outputs(self, command: str) -> list:
        """
        Build the standard Slivka outputs section:
        - main output file  (named after the tool, e.g. outfile.needle)
        - stdout log
        - stderr error-log

        The output name (e.g. "alignment" for needle, "sequence-info" for infoseq)
        is derived from EDAM_data options on the outfile parameter in analysis_extension,
        falling back to "output".
        """
        output_name  = self._detect_output_name(command)
        ext          = self.OUTFILE_EXT_MAP.get(command, "out")
        outfile_path = f"outfile.{ext}"
        media        = self.MEDIA_TYPE_MAP.get(ext, "text/plain")

        return [
            SlivkaOutput(name=output_name, path=outfile_path, media_type=media),
            SlivkaOutput(name="log",        path="stdout",     media_type="text/plain"),
            SlivkaOutput(name="error-log",  path="stderr",     media_type="text/plain"),
        ]

    def _detect_output_name(self, command: str) -> str:
        """
        Try to derive a meaningful output name from the EDAM_data annotation
        on the outfile parameter in analysis_extension.
        e.g. EDAM_data:1381 value="Sequence alignment (pair)" → "alignment"
        Falls back to command name or "output".
        """
        if self._ext is None:
            return "output"
        for param_el in self._ext.findall("parameter"):
            base = param_el.find("base")
            if base is None:
                continue
            if base.get("name") != "outfile":
                continue
            # Look for EDAM_data option
            for opt in base.findall("option"):
                if opt.get("name", "").startswith("EDAM_data:"):
                    val = opt.get("value", "")
                    # Simplify: take first word(s) before parenthesis
                    simplified = re.sub(r"\s*\(.*?\)", "", val).strip().lower()
                    simplified = re.sub(r"[^\w\s-]", "", simplified)
                    simplified = re.sub(r"\s+", "-", simplified)
                    if simplified:
                        return simplified
        # Last-resort fallbacks
        FALLBACKS = {
            "needle":   "alignment",
            "water":    "alignment",
            "infoseq":  "sequence-info",
            "pepstats": "protein-stats",
            "seqret":   "sequence",
        }
        return FALLBACKS.get(command, "output")