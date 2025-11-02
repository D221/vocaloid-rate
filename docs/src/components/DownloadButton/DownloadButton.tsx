import React, { useState, useEffect } from "react";
import styles from "./DownloadButton.module.css";

const downloads = {
  Windows:
    "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-windows.zip",
  Linux:
    "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-linux.zip",
  macOS:
    "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-macos.zip",
};

type OS = "Windows" | "Linux" | "macOS" | "Unknown";

function getOS(): OS {
  if (typeof window === "undefined") {
    return "Unknown";
  }

  const userAgent = window.navigator.userAgent;
  if (userAgent.indexOf("Win") !== -1) return "Windows";
  if (userAgent.indexOf("Mac") !== -1) return "macOS";
  if (userAgent.indexOf("Linux") !== -1) return "Linux";
  return "Unknown";
}

export default function DownloadButton() {
  const [os, setOs] = useState<OS>("Unknown");
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    setOs(getOS());
  }, []);

  const handleDownload = () => {
    if (os !== "Unknown") {
      window.location.href = downloads[os];
    }
  };

  const handleDropdownToggle = () => {
    setShowDropdown(!showDropdown);
  };

  const handleAlternativeDownload = (selectedOs: OS) => {
    if (selectedOs !== "Unknown") {
      window.location.href = downloads[selectedOs];
    }
    setShowDropdown(false);
  };

  return (
    <div className={styles.downloadContainer}>
      <button className={styles.downloadButton} onClick={handleDownload}>
        {os !== "Unknown" ? `Download for ${os}` : "Download"}
      </button>
      <div className={styles.dropdownContainer}>
        <button
          className={styles.dropdownToggle}
          onClick={handleDropdownToggle}
        >
          ▼
        </button>
        {showDropdown && (
          <ul className={styles.dropdownMenu}>
            {Object.keys(downloads).map((key: string) => (
              <li
                key={key}
                onClick={() => handleAlternativeDownload(key as OS)}
              >
                {key}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
