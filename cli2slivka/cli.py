from pathlib import Path

import click

from cli2slivka.generators.slivka import SlivkaYAMLWriter
from cli2slivka.parsers.base import CLIParser
from cli2slivka.parsers.registry import ParserRegistry
from cli2slivka.utils.xml import slugify


@click.command()
@click.option("--format", type=click.Choice(["acd", "galaxy"]))
@click.argument('inputs', type=click.Path(exists=True, dir_okay=True), required=True, nargs=-1)
def convert(format, inputs):
     parser: CLIParser | None = None
     if format:
          parser = ParserRegistry.get_by_format(format)

     for p in map(Path, inputs):
          if p.is_file():
               if not is_hidden(p):
                    process(parser, p)
          else:
               for file in p.rglob("*"):
                    if file.is_file() and not is_hidden(file):
                         process(parser, file)


def is_hidden(path: Path) -> bool:
     return any(part.startswith('.') for part in path.parts)

def process(parser: CLIParser, input: Path):
     parser = parser or ParserRegistry.detect(input)
     service = parser.parse(input)
     if service is not None:
          yaml_path = f"{slugify(service.name)}.service.yaml"
          writer = SlivkaYAMLWriter(service)
          writer.write(yaml_path)
     else:
          click.secho(f"Parsing of {input} failed", fg="red")

if __name__ == "__main__":
    convert()
