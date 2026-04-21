from pathlib import Path

import click

from cli2slivka.generators.slivka import SlivkaYAMLWriter
from cli2slivka.parsers.base import CLIParser
from cli2slivka.parsers.registry import ParserRegistry
from cli2slivka.utils.xml import slugify

### Connection of everything
# click tells that the function becomes a terminal command so you can 
# run something like python script.py convert --format galaxy file.xml

@click.command()
@click.option("--format", type=click.Choice(["acd", "galaxy"]))
@click.argument('inputs', type=click.Path(exists=True, dir_okay=True), required=True, nargs=-1) # accepting one or more paths
def convert(format, inputs): # Getting files and parsers
     parser: CLIParser | None = None
     if format:
          parser = ParserRegistry.get_by_format(format)

     for p in map(Path, inputs):
          if p.is_file():
               if not is_hidden(p):
                    process(parser, p)
          else: # if not file than folder
               for file in p.rglob("*"): # scan whole folder recursively for all files. 
                    if file.is_file() and not is_hidden(file):
                         process(parser, file)


def is_hidden(path: Path) -> bool:
     return any(part.startswith('.') for part in path.parts)

# ACTUALLY CREATING SERVICE
def process(parser: CLIParser, input: Path):
     parser = parser or ParserRegistry.detect(input) # if there was no parser with get_by_format then parser will be none but 
     # here a parser can be detected automatically.
     service = parser.parse(input)
     if service is not None:
          yaml_path = f"{slugify(service.name)}.service.yaml"
          writer = SlivkaYAMLWriter(service)
          writer.write(yaml_path)
     else:
          click.secho(f"Parsing of {input} failed", fg="red")

if __name__ == "__main__":
     convert()
