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
@click.option("--format", type=click.Choice(["acd", "galaxy", "soap"])) # should be required true because if not 
# set, than there are two different parsers that take suffix .xml as file type...
@click.argument('inputs', type=click.Path(exists=True , dir_okay=True), required=True, nargs=-1) # Accepting one or more paths as argument.
def convert(format, inputs):
     """Convert one or more tool definition files into Slivka YAML.

     Args:
          format: Optional explicit parser format name (e.g. 'galaxy', 'soap').
          inputs: One or more input file or directory paths.
     """
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
     """Return True when the given path points to a hidden file or directory.

     Args:
          path: The path to test.

     Returns:
          True if any path component starts with a dot.
     """
     return any(part.startswith('.') for part in path.parts)

# ACTUALLY CREATING SERVICE
def process(parser: CLIParser, input: Path):
     """Parse a single input file and write the generated Slivka YAML.

     Args:
          parser: Optional parser instance to use; if None, parser detection is attempted.
          input: Path to the input file to convert.
     """
     try:
          parser = parser or ParserRegistry.detect(input) # if there was no parser with get_by_format then parser will be none but 
          # here a parser can be detected automatically.
          if parser.can_parse(input) is False:
               raise ValueError
     except Exception:
          click.secho(f"Invalid file {input}", fg="red")
          return 

     try:
          service = parser.parse(input)
          if service is not None:
               yaml_path = f"generated_yamls/{slugify(service.name)}.service.yaml"
               writer = SlivkaYAMLWriter(service)
               writer.write(yaml_path)
          else:
               click.secho(f"Parsing of {input} failed", fg="red")
     except Exception:
          click.secho(f"Could not parse {input}", fg="red", err=True)
          return
if __name__ == "__main__":
     convert()
