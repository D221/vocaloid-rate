# Vocaloid Rate

Vocaloid Rate is a personal, self-hosted web application for tracking, rating, and exploring Vocaloid music rankings. It periodically scrapes data from [Vocaloard](https://vocaloard.injpok.tokyo/en/), providing a clean and feature-rich interface to manage a personal collection of rated tracks.

The application is built with a Python backend using FastAPI and a dynamic vanilla JavaScript frontend.

![Vocaloid Rater Screenshot](path/to/your/screenshot.png)

## Features

-   **Dynamic Track Table:** View the latest Top 300 Vocaloid tracks, with support for sorting by rank, title, producer, and more.
-   **Personal Ratings:** Rate songs on a 1-10 star scale. Your ratings are saved locally in a SQLite database.
-   **Interactive Filtering:**
    -   Filter by text search for Title (EN/JP), Producer, and Voicebank.
    -   Filter by rating status (Rated, Unrated, All).
    -   Filter by chart status (On Chart vs. Expired/Archived).
-   **Dedicated Rated Tracks Page:** A dashboard view of all your rated songs, featuring detailed statistics.
-   **Advanced Statistics:**
    -   View your average and median ratings.
    -   See your Top 10 favorite producers and voicebanks, calculated with a weighted Bayesian average.
    -   Interactive rating distribution chart to filter tracks by a specific score.
-   **Rich Media Integration:**
    -   Embed YouTube videos directly in the track list.
    -   Fetch and display song lyrics from the VocaDB API, with a language selector.
    -   Button to open the official song page on VocaDB.
-   **Smart Scraping:** The data update process is optimized to first check for changes in the rankings before running a full scrape, saving time and resources.
-   **Modern UI/UX:**
    -   Light and Dark mode, with automatic detection of system preference.
    -   (Not Ready) Fully responsive design with a horizontally scrolling table for mobile devices.
    -   Sleek skeleton loaders and debounced inputs for a smooth user experience.

## Tech Stack

-   **Backend:** FastAPI, SQLAlchemy, Uvicorn
-   **Frontend:** Vanilla JavaScript, HTML5, CSS3
-   **Database:** SQLite
-   **Data Scraping:** `requests`, `BeautifulSoup4`
-   **Charting:** Chart.js

## Installation & Setup

To run this project locally, follow these steps.

**1. Clone the repository:**
```bash
git clone https://github.com/D221/vocaloid-rate
cd vocaloid-rate
```
**3. Install the required packages:**

```bash
pip install -r requirements.txt
```

**4. Run the application:**
```bash
The application is served using Uvicorn. From the project root directory, run:

uvicorn app.main:app --reload

The application will be available at http://127.0.0.1:8000.
```

## How to Use

**Initial Scrape**: Upon first launch, the database will be empty. Click the "Update Tracks" button to perform the initial scrape of the Top 300 tracks.
**
Rate Songs**: Click the stars in the "My Rating" column to rate a track.

**Explore**: Use the filter and sort options to explore the music. Click on producer or voicebank names to quickly filter the list.

**View Rated Tracks**: Navigate to the "View Rated Tracks" page to see your personal collection and statistics.