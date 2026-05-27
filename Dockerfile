FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

COPY pyproject.toml uv.lock requirements.txt ./
COPY cli2slivka/ ./cli2slivka/

RUN uv pip install --system --no-cache -r requirements.txt

ADD testdata_SOAPLabXMLs.tar.gz /app/testdata_SOAPLabXMLs

ENTRYPOINT ["python", "-m", "cli2slivka.cli"]