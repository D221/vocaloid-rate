# Vocaloid Rate

> **Web Version:** Access the application at [vocaloid-rate.vercel.app](https://vocaloid-rate.vercel.app/).
> - **Note on Performance:** The web version may be significantly slower than running the application locally via the downloadable `.exe` due to cloud database latency.
> - **User Accounts:** You can create an account and log in. Passwords are securely hashed and encrypted.
> - **Privacy:** Emails are only used as usernames; we do not send any emails (including password resets). You can use a dummy email address if you prefer.

![Vocaloid Rater Screenshot](assets/main.png)

Vocaloid Rate is a personal, self-hosted web application for tracking, rating, and exploring Vocaloid music rankings. It scrapes data from [Vocaloard](https://vocaloard.injpok.tokyo/en/), providing a clean and feature-rich interface to manage your personal collection of rated tracks and playlists.

The application is built with a Python/FastAPI backend and a optimized vanilla JavaScript frontend using Tailwind CSS.

## Features

- **Dynamic Track Table:** View the latest Top 300 Vocaloid tracks with powerful sorting and filtering.
- **Personal Ratings & Notes:** Rate songs on a 1-10 star scale and add personal notes, all saved locally.
- **Interactive Filtering:**
  - Filter by text search for Title (EN/JP), Producer, and Voicebank.
  - Filter by your rating status (Rated, Unrated, All).
  - Filter by chart status (On Chart vs. Expired/Archived).
- **Custom Playlists:**
  - Create and manage multiple personal playlists.
  - Add or remove tracks from any playlist with a single click.
  - Use a drag-and-drop editor to set a custom order for your playlists.
  - Import and Export single playlists to share with others.
- **Dedicated Rated Tracks Page:** A dashboard view of all your rated songs, featuring detailed statistics.
- **Advanced Statistics:**
  - View your average and median ratings.
  - See your Top 10 favorite producers and voicebanks.
  - Interactive rating distribution chart to filter tracks by a specific score.
- **Rich Media Integration:**
  - Integrated music player with both audio-only and embedded video modes.
  - Player controls for shuffle, repeat, and volume.
  - Fetch and display song lyrics from the VocaDB API.
- **UI/UX:**
  - Light and Dark mode with automatic system preference detection.
  - Fully responsive design that adapts from desktop to a mobile-friendly card layout.

<details>
<summary><strong>Click to see more screenshots</strong></summary>

### Embed Playback (main feature)

![Embed View](assets/embeds.png)

### Filtering and Sorting

![Filter View](assets/filter.png)

### Ratings Page

![Ratings View](assets/ratings.png)

### Options Mode

![Options Mode](assets/options.png)

### Playlists

![Playlist List View](assets/playlists.png)

### Playlist Editor

![Playlist Edit View](assets/playlist-edit.png)

### Mobile UI

![Mobile View](assets/mobile.png)

</details>

## Deployment Options

Vocaloid Rate supports two primary deployment modes:

### 1. Self-Hosted (SQLite)
This is the default mode, ideal for local use or hosting on a private server (e.g., via Docker).
- **Database:** SQLite (stored in `data/tracks.db`).
- **Setup:** Just run the application. No additional configuration is required.
- **Persistent Data:** Ensure the `data` directory is persisted.

### 2. Cloud Deployment (Vercel + Postgres)
The application is pre-configured for deployment on Vercel using a PostgreSQL database (e.g., Vercel Postgres, Supabase, or Railway).
- **Database:** PostgreSQL (or any other DB supported by SQLAlchemy).
- **Environment Variables:**
  - `DATABASE_URL`: Your database connection string (e.g., `postgres://user:password@host:port/dbname`).
  - `SECRET_KEY`: A long, random string for JWT authentication.
  - `CRON_SECRET`: (Optional) A secret key to protect the scraping cron endpoint.
- **Vercel Setup:**
  - Connect your repository to Vercel.
  - Configure the environment variables in the Vercel dashboard.
  - The application will automatically run migrations on startup.

---

## Installation (for End-Users)

This application is designed to be easy to run on your personal computer. No technical knowledge of Python or Docker is required.

### 1. Download the Latest Release

Go to the [**Releases Page**](https://github.com/D221/vocaloid-rate/releases/latest) on GitHub.

- For **Windows**, download the `vocaloid-rate-windows.zip` file.
- For **macOS**, download the `vocaloid-rate-macos.zip` file.
- For **Linux**, download the `vocaloid-rate-linux.zip` file.

### 2. Extract the ZIP File

Unzip the downloaded file to a permanent location on your computer (e.g., your Desktop or a folder in your user directory).

### 3. Run the Application

- **On Windows:** Double-click the **`vocaloid-rate.exe`** file.
- **On macOS / Linux:** Double-click the **`vocaloid-rate`** binary file. (On first run, you may need to right-click and choose "Open" to bypass security warnings).

A terminal window will open, and after a moment, your default web browser will automatically open to `http://localhost:8000`. The application is now running.

### 4. Stop the Application

To stop the server, simply close the terminal window that opened in the previous step.

## Advanced Installation (Docker)

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

- **Python 3.8+** and **uv**.
- **Node.js & npm** or **Bun**.

### 1. Clone the Repository

```bash
git clone https://github.com/D221/vocaloid-rate
cd vocaloid-rate
```

### 2. Install Dependencies

First, create a Python virtual environment and install the required packages.

```bash
# Install uv (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install uv (Windows)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install Python packages
uv sync
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

## Production and Release

### Building for Production

To create a production-ready build of all static assets (minified CSS and JavaScript), run the following command:

```bash
bun run build
```

### Creating a Distributable Release

To bundle the entire application into a simple, self-contained `.zip` file for end-users who do not have Python or Node.js installed, run the release script:

```bash
bun run release
```

This fully automated process will:

1.  Run the `build` command to generate production assets.
2.  Use `PyInstaller` to bundle the FastAPI application and a Python interpreter into a single executable.
3.  Clean up unnecessary source files (like `input.css` and non-minified `.js` files) from the final package.
4.  Create a `vocaloid-rate-release.zip` file in dist directory, containing the executable and all necessary files for an end-user to run the application.

## APIs Used

This project integrates with several external APIs to provide its features.

- **[Vocaloard](https://vocaloard.injpok.tokyo/en/):** The primary source of song data. The application scrapes the Top 300 rankings directly from this site.

- **[VocaDB](https://vocadb.net/):** Used to fetch lyrics for the songs. The application makes API calls to VocaDB to retrieve lyrics based on the song title and artist.

- **[YouTube](https://www.youtube.com/):** Used for the embedded video player. The application embeds the YouTube player to stream the music videos for the songs.
