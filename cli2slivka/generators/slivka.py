
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
        self.service = service

    def write(self, path: str) -> None:
        Path(path).write_text(self.to_yaml(), encoding="utf-8")
        print(f"Written: {path}")

    def to_yaml(self) -> str:
        s   = self.service
        out = ["---"]

        out += [
            f"slivka-version: {s.slivka_version}",
            f"name: {s.name}",
        ]
        if s.description:
            out.append(f"description: {s.description}")
        out.append(f"version: '{s.version}'")
        out.append(f"license: {s.license}")

        if s.classifiers:
            out.append("classifiers:")
            for c in s.classifiers:
                out.append(f"  - '{c}'")

        out += ["", "parameters:"]
        for p in s.parameters:
            out.append(f"  {p.slug}:")
            for k, v in p.to_dict().items():
                out += self._render_field(k, v, indent=4)

        out += ["", f"command: {s.command}", "", "args:"]
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
        return "\n".join(out)

    def _render_field(self, key: str, value, indent: int = 4) -> list:
        pad   = " " * indent
        lines = []
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            for k, v in value.items():
                lines.append(f"{pad}  {k}: {v}")
        elif isinstance(value, bool):
            lines.append(f"{pad}{key}: {'true' if value else 'false'}")
        elif isinstance(value, str) and any(c in value for c in ':{}[]|>&*!,%@`"\'#\\'):
            escaped = value.replace('"', '\\"')
            lines.append(f'{pad}{key}: "{escaped}"')
        else:
            lines.append(f"{pad}{key}: {value}")
        return lines