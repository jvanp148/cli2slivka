
import argparse
from cli2slivka.utils.xml import slugify
from cli2slivka.parsers.galaxy import GalaxyXMLParser
from cli2slivka.generators.slivka import  SlivkaYAMLWriter

# ===========================================================================
# CLI
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Galaxy XML tool wrapper to a Slivka service YAML."
    )
    parser.add_argument("xml",  help="Path to the Galaxy XML file")
    parser.add_argument("yaml", nargs="?", help="Output YAML path (optional)")
    cli = parser.parse_args()

    service   = GalaxyXMLParser(cli.xml).parse()
    yaml_path = cli.yaml or f"{slugify(service.name)}.service.yaml"
    SlivkaYAMLWriter(service).write(yaml_path)


if __name__ == "__main__":
    main()