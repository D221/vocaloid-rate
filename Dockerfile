# =================================================================
# STAGE 1: Frontend Build Environment ("The Builder")
# We use an official Bun image, which is fast and lightweight.
# =================================================================
FROM oven/bun:1 as builder

# Set the working directory for the frontend build
WORKDIR /app/frontend

# Copy package management files first to leverage Docker layer caching
COPY package.json bun.lock ./
COPY eslint.config.mjs .

# Install ALL dependencies (including devDependencies) needed for the build
RUN bun install --frozen-lockfile

# Copy the frontend source code that needs to be built
COPY app/static/css/input.css ./app/static/css/input.css
COPY app/static/js/ ./app/static/js/
COPY app/templates/ ./app/templates/

# Run the production build command from your package.json
# This will create app/static/css/app.css and the *.min.js files
RUN bun run build


# =================================================================
# STAGE 2: Final Python Runtime Environment
# =================================================================
FROM python:3.13-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python application source code
COPY ./app ./app

# --- This is the crucial step ---
# Copy ONLY the built static assets from the "builder" stage.
# This copies the final app.css, *.min.js, and all other static assets
# like images and the manifest file.
COPY --from=builder /app/frontend/app/static/ /app/static/

# Copy the templates (which are also needed at runtime)
COPY --from=builder /app/frontend/app/templates/ /app/templates/

EXPOSE 8000

# The command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]