FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONHASHSEED=0

ENTRYPOINT ["python", "-m", "workload.agent"]

CMD ["--n", "45", "--seed", "42"]
