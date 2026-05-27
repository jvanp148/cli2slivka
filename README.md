# cli2slivka

Convert CLI tool definitions into **Slivka-compatible YAML services**.

`cli2slivka` parses tool definitions (currently SOAP/XML) into a **canonical intermediate model**, and then generates a valid Slivka YAML specification.

## Features

* Parse **SOAP XML (Soaplab2 / EMBOSS-style)** tool definitions
* Convert into a structured **canonical model (`SlivkaService`)**
* Generate **Slivka YAML service files**
* Extensible parser system (ACD, Galaxy planned)
* Automatic CLI argument and parameter reconstruction
* Docker containerization of this CLI application

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

## Prerequisites

* [Python 3.10+](https://www.python.org/)
* [uv](https://docs.astral.sh/uv/) — fast Python package and environment manager (`sudo dnf install uv`)
* [Git LFS](https://git-lfs.github.com/) — required to download the test data archive (`testdata_SOAPLabXMLs.tar.gz`)
* [Docker](https://docs.docker.com/get-docker/) — optional, for running the containerized version

## Installation

### 1. Clone the repository

Git LFS must be initialized before cloning so the test data archive is downloaded correctly:

```bash
git lfs install
git clone https://github.com/jvanp148/cli2slivka.git   # HTTPS
# or
git clone git@github.com:jvanp148/cli2slivka.git       # SSH
```

If you already cloned without Git LFS, pull the LFS-tracked files manually:

```bash
git lfs pull
```

### 2. Set up the environment

This project uses [uv](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
uv venv
source ./venv/bin/activate
uv sync   # installs all packages from uv.lock
```

## Usage

### Basic command

What do you need:

* The **format**, specified with `--format`, can be `soap`, `galaxy`, or `acd`, depending on which parsers are available
* The **output directory**, specified with `--outdir` — a path to a folder (existing or not) where YAML outputs will be written
* **Input** — one or more files or a directory, passed as the last argument

Use on one XML file:

```bash
python -m cli2slivka.cli --format soap --outdir path/to/outdir/ path/to/file.xml
```

Or on a directory:

```bash
python -m cli2slivka.cli --format soap --outdir path/to/outdir/ path/to/xmlfiles/folder/
```

### Without specifying format

The parser registry will attempt **auto-detection**:

```bash
python -m cli2slivka.cli --outdir path/to/outdir/ path/to/xmlfiles/folder/
```

### Without specifying outdir

The output directory defaults to `generated_yamls/` in the current working directory:

```bash
python -m cli2slivka.cli --format soap path/to/xmlfiles/folder/
```

### Using the included test data

The repository includes a tar archive of Soaplab2 XML files for all EMBOSS tools tracked via Git LFS (`testdata_SOAPLabXMLs.tar.gz`). Extract it first, then run the parser on it:

```bash
tar -xzf testdata_SOAPLabXMLs.tar.gz
python -m cli2slivka.cli --format soap --outdir generated_yamls/ testdata_SOAPLabXMLs/
```

## Output

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

## Supported Formats

| Format     | Status         |
| ---------- | -------------- |
| SOAP XML   | ✅ Implemented |
| Galaxy XML | 🚧 In progress |
| EMBOSS ACD | 🚧 Planned     |

## How It Works (Deep Dive)

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

Then add it to `cli2slivka/parsers/__init__.py`:

```python
from cli2slivka.parsers.parserfilename import MyParser
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
* Generated YAMLs are specific to use as Slivka services

## Docker

A `Dockerfile` is included to containerize the `cli2slivka` application. Build the image from inside the project folder:

```bash
docker build -t cli2slivka:1.0 .
```

Mount your local input and output directories to run the converter:

```bash
docker run --rm \
  -v "/path/to/local/inputs":/inputs \
  -v "/path/to/local/outputs":/outputs \
  cli2slivka:1.0 --format soap --outdir /outputs /inputs
```

**Example — parse local XML files:**

```bash
docker run --rm \
  -v "$(pwd)"/soapdata:/inputs \
  -v "$(pwd)"/generated_yamls:/outputs \
  cli2slivka:1.0 --format soap --outdir /outputs /inputs
```

**Example — use the bundled test data (Git LFS):**

The `testdata_SOAPLabXMLs.tar.gz` archive is tracked via Git LFS and is included in the Docker image at `/app/testdata_SOAPLabXMLs`. Make sure you have run `git lfs pull` before building the image so the archive is present locally.

```bash
docker run --rm \
  -v "$(pwd)"/generated_yamls:/outputs \
  cli2slivka:1.0 --format soap --outdir /outputs /app/testdata_SOAPLabXMLs
```

A `generated_yamls/` folder will appear in your working directory containing the generated YAML files.

## Git LFS

This repository uses [Git LFS](https://git-lfs.github.com/) to track large test data files (currently `testdata_SOAPLabXMLs.tar.gz`).

Install Git LFS and initialize it before cloning:

```bash
git lfs install
```

If you cloned without Git LFS, fetch the tracked files afterwards:

```bash
git lfs pull
```

Without this step, the tar archive will appear as a small pointer file rather than the actual data.

## Credits

* [Barton Group](https://github.com/bartongroup) — [Slivka](https://github.com/bartongroup/slivka) REST API framework and [slivka-bio-docker](https://github.com/bartongroup/slivka-bio-docker)
* [Soaplab2](http://soaplab.sourceforge.net/soaplab2/) — SOAP-based web services for EMBOSS, whose XML format is the primary input format supported
* [EMBOSS](https://emboss.sourceforge.net/) — European Molecular Biology Open Software Suite, the bioinformatics toolkit whose tools this project helps configure
* [uv](https://docs.astral.sh/uv/) — Python package and environment manager used in this project
* [Git LFS](https://git-lfs.github.com/) — used for tracking large test data files
