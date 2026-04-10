# Use the official Python slim image (Debian-based, glibc)
FROM python:3.13-slim

# Set environment variables for Python to optimize runtime and set timezone
ENV TZ=Asia/Kolkata \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMPOSE_BAKE=true \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_HTTP_TIMEOUT=90 \
    UV_NO_PROGRESS=1 \
    UV_CONCURRENT_DOWNLOADS=10

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        curl \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy the uv and uvx binaries from the official uv image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy only dependency files first for better Docker cache utilization
COPY ./pyproject.toml uv.lock ./

# Install dependencies with BuildKit cache mount for uv cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Adding Aliases
RUN echo 'alias ipython="uv run ipython"' >> /root/.bashrc

# Copy the entire application code into the container
COPY . .

# Install the project itself (deps already cached from above)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

EXPOSE 8001 8000 8005 8010