---
sidebar_position: 2
---

# Advanced Installation

## Docker

For users familiar with Docker, you can run the application using the pre-built image from the GitHub Container Registry.

### 1. Create `docker-compose.yml`

```yaml
services:
  web:
    image: ghcr.io/d221/vocaloid-rate:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 2. Run the Container

```bash
docker compose up -d
```

### 3. Access the Application:

- The application will be available at `http://localhost:8000`.
  > **Important:** You must use `localhost` and not the IP address `127.0.0.1`. Using the IP address will cause the YouTube video embeds to fail due to API security policies.

### 4. How to Stop:

```bash
docker compose down
```

## Development Setup

This project uses a Python/FastAPI backend and a JavaScript frontend with a full build system. To contribute or modify the code, you will need both Python and a Node.js-compatible runtime like Node.js or Bun.

### Prerequisites

- **Python 3.8+** and `pip`.
- **Node.js & npm** or **Bun**.

### 1. Clone the Repository

```bash
git clone https://github.com/D221/vocaloid-rate
cd vocaloid-rate
```

### 2. Install Dependencies

First, create a Python virtual environment and install the required packages.

```bash
# Create and activate a virtual environment (macOS/Linux)
python3 -m venv venv
source venv/bin/activate

# Create and activate a virtual environment (Windows)
python -m venv venv
.\venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

Next, install the Node.js development dependencies. This will also set up the pre-commit hooks via Husky.

```bash
# Using Bun (recommended)
bun install

# Or using npm
npm install
```

### 3. Running the Development Environment

The development environment requires three processes to run concurrently: the FastAPI server, the Tailwind CSS compiler, and the JavaScript minifier. The project is configured to handle all of this with a single command.

Open your terminal and run:

```bash
bun run dev
```

This command uses `concurrently` to:

1.  Start the FastAPI backend server with **hot-reloading**.
2.  Start the Tailwind compiler in **watch mode**, which automatically builds and minifies `app.css` on any change.
3.  Start a file watcher (`chokidar`) that automatically runs `terser` to build and minify all `*.min.js` files whenever you save a source `.js` file.

Once running, access the application at `http://localhost:8000`. You can now edit your source `.py`, `.js`, and `input.css` files, and all changes will be reflected automatically.

### 4. Code Formatting and Linting

This project uses Prettier, ESLint, and Ruff to ensure a consistent code style. These are configured to run automatically before each commit using Husky and `lint-staged`.

You can also run them manually:

- **Format all files:** `bun run format`
- **Check for linting errors:** `bun run lint`
- **Attempt to automatically fix linting errors:** `bun run lint:fix`
