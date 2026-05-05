# cli2slivka

Convert CLI tool definitions into **Slivka-compatible YAML services**.

`cli2slivka` parses tool definitions (currently SOAP/XML) into a **canonical intermediate model**, and then generates a valid Slivka YAML specification.

## Features

* Parse **SOAP XML (Soaplab2 / EMBOSS-style)** tool definitions
* Convert into a structured **canonical model (`SlivkaService`)**
* Generate **Slivka YAML service files**
* Extensible parser system (ACD, Galaxy planned)
* Automatic CLI argument and parameter reconstruction

## Core Idea

Different workflow systems describe CLI tools in different/incompatible formats.

This project solves that by introducing a **canonical intermediate model**. This canonical model is basically a standardized internal representation of a tool definition, independent of the original input format, allowing different formats to be parsed into a single unified structure.

```bash
Input Format (SOAP XML, Galaxy XML, ACD, ...)
                ↓
        Parser (format-specific)
                ↓
      SlivkaService (canonical model)
                ↓
     YAML Generator (Slivka output)
```

This separation makes the system:

* extensible (add new parsers easily)
* maintainable (logic lives in one place)
* consistent (all outputs follow the same schema)

## Project Structure

```bash
cli2slivka/
│
├── __init__.py
│
├── cli.py                 # Entry point (CLI interface)
│
├── model/
│   └── canonical.py       # Core data model (SlivkaService, Parameters, Args)
│
├── parsers/
│   ├── __init__.py
│   ├── base.py            # Abstract parser interface
│   ├── soap_xml.py        # SOAP XML parser (current main implementation)
│   ├── galaxy.py          # Galaxy XML parser (WIP)
│   └── registry.py        # Parser auto-discovery / selection
│
├── generators/
│   └── slivka.py          # YAML writer
│
└── utils/
    ├── xml.py
    └── yaml.py
```

## Installation

Clone this git repository:

```bash
git clone https://github.com/JulieVanPouckeBIT/cli2slivka.git # through https
git clone git@github.com:JulieVanPouckeBIT/cli2slivka.git # through ssh
```

This project is designed to run in a **UV environment**. If you do not have uv installed yet, run `sudo dnf install uv`.

```bash
uv venv
source ./venv/bin/activate
uv sync # all packages and dependencies inside uv.lock will be installed
```

## Usage

### Basic command

What do you need:

* The **format**, specified with `--format`, can be soap, galaxy, acd, depending on which parsers are available
* The **output directory**, specified as `--outdir` which should be a string of the path to a folder (existing or not) where the yaml outputs can be placed
* **Input**: last argument and can also be multiple files places after one another

Use on one xml file:

```bash
python -m cli2slivka.cli --format soap --outdir path/to/outdir/ path/to/file.xml
```

Or on a directory:

```bash
python -m cli2slivka.cli --format soap --outdir path/to/outdir/ path/to/xmlfiles/folder/
```

### Without specifying format

The parser registry will attempt **auto-detection**.

```bash
python -m cli2slivka.cli --outdir path/to/outdir/ path/to/xmlfiles/folder/
```

### Without specifying outdir

The output directory will by default be `generated_yamls/` and placed in the pwd.

```bash
python -m cli2slivka.cli --format soap path/to/xmlfiles/folder/
```

## 📤 Output

Generated YAML files are written to:

```bash
outdir/<tool-name>.service.yaml
```

Example:

```yaml
name: water
command: water
parameters:
  asequence:
    type: file
```

## 🔍 Supported Formats

| Format     | Status         |
| ---------- | -------------- |
| SOAP XML   | ✅ Implemented |
| Galaxy XML | 🚧 In progress |
| EMBOSS ACD | 🚧 Planned     |

## ⚙️ How It Works (Deep Dive)

### 1. CLI Layer (`cli.py`)

* Handles user input (files / directories)
* Selects parser via `ParserRegistry`
* Runs parsing + YAML generation

### 2. Parser Layer

All parsers implement:

```python
class CLIParser:
    def can_parse(path) -> bool
    def parse(path) -> SlivkaService
```

#### SOAP Parser Highlights

* Detects `<analysis>` root

* Extracts:

  * metadata (name, version, description)
  * parameters (with type inference)
  * EDAM classifiers
  * CLI arguments
  * outputs

* Handles:

  * sequence parameters + qualifiers (`sformat`, `sbegin`, etc.)
  * automatic grouping and ordering
  * output detection via `iotype="output"`

### 3. Canonical Model (`SlivkaService`)

Central object representing a CLI tool:

* Parameters (`File`, `Text`, `Integer`, `Decimal`, `Choice`)
* Arguments (mapping to CLI flags)
* Outputs
* Metadata

Example:

```python
service = SlivkaService(
    name="water",
    command="water"
)
```

### 4. YAML Generator

`SlivkaYAMLWriter`:

* Converts `SlivkaService` → YAML
* Handles quoting, formatting, and structure
* Produces valid Slivka service specs

## Extending the Project

### Add a new parser

Create a class:

```python
@register_parser
class MyParser(CLIParser):
    formats = ("myformat",)

    def can_parse(self, path):
        ...

    def parse(self, path):
        return SlivkaService(...)
```

Done — it will be auto-registered.

### Customize a specific tool

Override `post_process()`:

```python
class NeedleParser(SoapXMLParser):
    def post_process(self, service):
        param = service.get_parameter("gapopen")
        if param:
            param.max_val = 100.0
```

## Limitations

* SOAP parsing assumes Soaplab2-style structure
* Some edge-case parameters may be skipped silently
* Output detection relies on `analysis_extension`
* The generated YAMLs are specific for the use as Slivka services
