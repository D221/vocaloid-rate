# =================================================================
# STAGE 1: Unified Build Environment ("The Builder")
# This stage has both Python and Bun to build all assets:
# - Frontend (CSS, JS) via Bun/Tailwind/Terser
# - Translations (.mo files) via Python/PyBabel
# =================================================================
FROM python:3.13 AS builder

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:${PATH}"

WORKDIR /app

# Copy configuration and dependency files first for caching
COPY requirements.txt package.json bun.lock babel.cfg ./

# Install both Python and Bun dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN bun install --frozen-lockfile

# Copy the entire application source code
# This includes /app, /locales, and any other root files needed for the build
COPY . .

# Run the unified production build command from your package.json
# This now correctly runs `i18n:compile`, `build:css`, and `build:js`
RUN bun run build


# =================================================================
# STAGE 2: Final Python Runtime Environment
# This stage is a slim Python image containing ONLY what's needed to run.
# =================================================================
FROM python:3.13-slim

WORKDIR /app

# Copy requirements.txt from the builder and install only runtime dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python application source code from the builder
COPY --from=builder /app/app ./app

# Copy the final, compiled static assets from the builder
COPY --from=builder /app/app/static/ ./app/static/

# Copy the templates from the builder
COPY --from=builder /app/app/templates/ ./app/templates/

# Copy the compiled translation files ---
# This is the crucial step to include your .mo files in the final image
COPY --from=builder /app/locales/ ./locales/

# Copy Alembic configuration ---
COPY --from=builder /app/alembic.ini .
COPY --from=builder /app/alembic/ ./alembic/

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

# Set the entrypoint to our script
ENTRYPOINT ["entrypoint.sh"]

# The command to run. This gets passed as arguments ("$@") to entrypoint.sh
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]