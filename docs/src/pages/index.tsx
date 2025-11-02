import type { ReactNode } from "react";
import clsx from "clsx";
import Link from "@docusaurus/Link";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Layout from "@theme/Layout";
import Heading from "@theme/Heading";
import ImageGallery from "react-image-gallery";
import type { ReactImageGalleryItem } from "react-image-gallery";
import "react-image-gallery/styles/css/image-gallery.css";

import styles from "./index.module.css";

import DownloadButton from "@site/src/components/DownloadButton/DownloadButton";

const images: ReactImageGalleryItem[] = [
  {
    original: "/vocaloid-rate/img/main.png",
    thumbnail: "/vocaloid-rate/img/main.png",
    description: "Main page screenshot",
  },
  {
    original: "/vocaloid-rate/img/embeds.png",
    thumbnail: "/vocaloid-rate/img/embeds.png",
    description: "Embeds screenshot",
  },
  {
    original: "/vocaloid-rate/img/filter.png",
    thumbnail: "/vocaloid-rate/img/filter.png",
    description: "Filter functionality screenshot",
  },
  {
    original: "/vocaloid-rate/img/ratings.png",
    thumbnail: "/vocaloid-rate/img/ratings.png",
    description: "Ratings page screenshot",
  },
  {
    original: "/vocaloid-rate/img/playlists.png",
    thumbnail: "/vocaloid-rate/img/playlists.png",
    description: "Playlists page screenshot",
  },
  {
    original: "/vocaloid-rate/img/playlist-edit.png",
    thumbnail: "/vocaloid-rate/img/playlist-edit.png",
    description: "Playlist edit page screenshot",
  },
  {
    original: "/vocaloid-rate/img/options.png",
    thumbnail: "/vocaloid-rate/img/options.png",
    description: "Options page screenshot",
  },
  {
    original: "/vocaloid-rate/img/mobile.png",
    thumbnail: "/vocaloid-rate/img/mobile.png",
    description: "Mobile view screenshot",
  },
];

function HomepageHeader() {
  const { siteConfig } = useDocusaurusContext();
  return (
    <header className={clsx("hero hero--primary", styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
      </div>
    </header>
  );
}

function renderImage(item: ReactImageGalleryItem) {
  return (
    <div className={styles["image-gallery-image"]}>
      <img src={item.original} alt={item.description} />
      {item.description && (
        <span className={styles["image-gallery-description"]}>
          {item.description}
        </span>
      )}
    </div>
  );
}

export default function Home(): ReactNode {
  const { siteConfig } = useDocusaurusContext();
  return (
    <Layout
      title={`${siteConfig.title}`}
      description="Description will go into a meta tag in <head />"
    >
      <HomepageHeader />
      <main>
        <section className="margin-vert--lg container">
          <div className={styles.center}>
            <DownloadButton />
          </div>
        </section>

        <section className="margin-vert--lg container">
          <h2>About the Project</h2>
          <p>
            Vocaloid Rate is a personal, self-hosted web application for
            tracking, rating, and exploring Vocaloid music rankings. It scrapes
            data from [Vocaloard](https://vocaloard.injpok.tokyo/en/), providing
            a clean and feature-rich interface to manage your personal
            collection of rated tracks and playlists.
          </p>
          <p>
            The application is built with a Python/FastAPI backend and a
            optimized vanilla JavaScript frontend using Tailwind CSS.
          </p>
          <h3>Features</h3>
          <ul>
            <li>
              <strong>Dynamic Track Table:</strong> View the latest Top 300
              Vocaloid tracks with powerful sorting and filtering.
            </li>
            <li>
              <strong>Personal Ratings & Notes:</strong> Rate songs on a 1-10
              star scale and add personal notes, all saved locally.
            </li>
            <li>
              <strong>Interactive Filtering:</strong> Filter by text search,
              rating status, and chart status.
            </li>
            <li>
              <strong>Custom Playlists:</strong> Create, manage, and share
              multiple personal playlists with a drag-and-drop editor.
            </li>
            <li>
              <strong>Dedicated Rated Tracks Page:</strong> A dashboard view of
              all your rated songs, featuring detailed statistics.
            </li>
            <li>
              <strong>Advanced Statistics:</strong> View your average and median
              ratings, top producers, and voicebanks.
            </li>
            <li>
              <strong>Rich Media Integration:</strong> Integrated music player
              with audio-only and embedded video modes, plus lyrics from VocaDB.
            </li>
            <li>
              <strong>UI/UX:</strong> Light and Dark mode with a fully
              responsive design.
            </li>
          </ul>
        </section>

        <section className="margin-vert--lg container">
          <h2>Installation</h2>
          <ol>
            <li>
              <strong>Download the Latest Release:</strong> Click the "Download"
              button above.
            </li>
            <li>
              <strong>Extract the ZIP File:</strong> Unzip the downloaded file
              to a permanent location on your computer.
            </li>
            <li>
              <strong>Run the Application:</strong> Double-click the
              `vocaloid-rate.exe` (Windows) or `vocaloid-rate` (macOS/Linux)
              file.
            </li>
            <li>
              <strong>Stop the Application:</strong> To stop the server, simply
              close the terminal window.
            </li>
          </ol>
        </section>

        <section className="margin-vert--lg container">
          <h2>Screenshots</h2>
          <ImageGallery items={images} renderItem={renderImage} />
        </section>
      </main>
    </Layout>
  );
}
