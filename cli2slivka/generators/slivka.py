
from pathlib import Path
from cli2slivka.model.canonical import SlivkaService
# ===========================================================================
# SlivkaYAMLWriter
# ===========================================================================

class SlivkaYAMLWriter:
    """
    Serialises a SlivkaService to a Slivka-compatible YAML file.
    No external dependencies — uses plain string building.
    """

    def __init__(self, service: SlivkaService):
        """Create a Slivka YAML writer for the given service.

        Args:
            service: SlivkaService instance to serialize.
        """
        self.service = service

    def write(self, path: str) -> None:
        """Write the Slivka YAML serialization to a file.

        Args:
            path: Output file path where YAML is written.
        """
        Path(path).write_text(self.to_yaml(), encoding="utf-8")
        print(f"Written: {path}")

    def to_yaml(self) -> str:
        """Serialize the SlivkaService to YAML text.

        Returns:
            The generated YAML document as a string.
        """
        s   = self.service
        out = ["---"]

        out += [
            f"slivka-version: {s.slivka_version}",
            f"name: {s.name}",
        ]
        if s.description:
            out.append(f"description: {s.description}")
        out.append(f"version: '{s.version}'")

        if s.author:
            out.append(f"author: {s.author}")
        
        out.append(f"license: {s.license}")
        
        if s.classifiers:
            out.append("classifiers:")
            for c in s.classifiers:
                out.append(f"- '{c}'")

        out += ["", "parameters:"]
        for p in s.parameters:
            out.append(f"  {p.slug}:")
            for k, v in p.to_dict().items():
                out += self._render_field(k, v, indent=4)

        out += ["", f"command: {s.command}", "", "args:"] #%# we want to have command as a list so this is done differently, go to soap python
        for arg in s.args:
            out.append(f"  {arg.slug}:")
            for k, v in arg.to_dict().items():
                out.append(f"    {k}: {v}")

        out += ["", "outputs:"]
        for o in s.outputs:
            out.append(f"  {o.name}:")
            for k, v in o.to_dict().items():
                out.append(f"    {k}: {v}")

        out += [
            "",
            "execution:",
            "  runners:",
            "    default:",
            "      type: SlivkaQueueRunner",
            "...",
            "",
        ]
        #%# also added the thing for tests, but this is unnecessary...
        return "\n".join(out)
    @staticmethod
    def _needs_quoting(s: str) -> bool:
        """
        Return True when a YAML plain scalar would be ambiguous or invalid.
        Applies to both keys and values inside a mapping.
 
        Rules:
        - Empty string
        - Starts with a YAML indicator: - + ? : & * ! | > ' " % @ `
        - Would be parsed as a non-string scalar (number, bool, null)
        - Contains structurally significant characters: : # { } [ ] ,
        """
        if not s:
            return True
        YAML_INDICATORS = set('-+?:&*!|>\'"%@`')
        if s[0] in YAML_INDICATORS:
            return True
        YAML_RESERVED = {'~', '.inf', '-.inf', '.nan'}   # {'true', 'false', 'yes', 'no', 'on', 'off', 'null', '~', '.inf', '-.inf', '.nan'}
        if s.lower() in YAML_RESERVED:
            return True
        try:
            float(s)
            return True
        except ValueError:
            pass
        if any(c in s for c in ':{}[]|>#,\\'):
            return True
        return False
 
    @staticmethod
    def _quote(s: str) -> str:
        """Wrap string in double quotes, escaping any internal double quotes."""
        escaped = s.replace('"', '\\"')
        return '"' + escaped + '"'
 
    def _render_field(self, key: str, value, indent: int = 4) -> list:
        """Render a YAML mapping field, quoting values when required.

        Args:
            key: Mapping key.
            value: Mapping value, which may be a scalar or dict.
            indent: Number of leading spaces for the rendered lines. By default 4 spaces (2 levels).

        Returns:
            A list of YAML lines representing the field.
        """
        pad   = ' ' * indent
        lines = []
        if isinstance(value, dict):
            lines.append(f'{pad}{key}:')
            for k, v in value.items():
                k_str = str(k)
                v_str = str(v)
                k_out = self._quote(k_str) if self._needs_quoting(k_str) else k_str
                v_out = self._quote(v_str) if self._needs_quoting(v_str) else v_str
                lines.append(f'{pad}  {k_out}: {v_out}')
        elif isinstance(value, bool):
            lines.append(f"{pad}{key}: {'true' if value else 'false'}")
        elif isinstance(value, str) and self._needs_quoting(value):
            lines.append(f'{pad}{key}: {self._quote(value)}')
        else:
            lines.append(f'{pad}{key}: {value}')
        return lines