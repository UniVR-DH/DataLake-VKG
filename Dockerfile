# Install uv
FROM python:3.12-slim
RUN pip install uv --root-user-action=ignore

# Install git-lfs for large file support
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends git-lfs && rm -rf /var/lib/apt/lists/*

# Change the working directory to the `app` directory
WORKDIR /app

# Copy `pyproject.toml` into the image
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md

# Install dependencies
RUN uv sync --no-install-project

# Copy the project into the image as an importable package
COPY datalake-vkg-api /app/datalake_vkg_api
RUN touch /app/datalake_vkg_api/__init__.py \
    /app/datalake_vkg_api/resources/__init__.py \
    /app/datalake_vkg_api/tools/__init__.py \
    /app/datalake_vkg_api/tools/setup/__init__.py \
    /app/datalake_vkg_api/tools/mapping/__init__.py

# Sync the project
RUN uv sync

ENV PYTHONPATH=/app

CMD ["uv", "run", "uvicorn", "datalake_vkg_api.main:app", "--host", "0.0.0.0", "--port", "5000"]