import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: "Vocaloid Rate",
  tagline: "A web application for rating and organizing Vocaloid songs.",
  favicon: "img/favicon.ico",

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // Set the production url of your site here
  url: "https://d221.github.io",
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: "/vocaloid-rate/",

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "d221", // Usually your GitHub org/user name.
  projectName: "vocaloid-rate", // Usually your repo name.

  onBrokenLinks: "throw",

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./src/sidebars.ts",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: "img/docusaurus-social-card.jpg",
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: "Vocaloid Rate",
      logo: {
        alt: "Vocaloid Rate Logo",
        src: "img/favicon-32x32.png",
      },
      items: [
        {
          to: "/docs/intro",
          label: "Docs",
          position: "left",
        },
        {
          label: "Download",
          position: "left",
          items: [
            {
              label: "Windows",
              href: "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-windows.zip",
            },
            {
              label: "Linux",
              href: "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-linux.zip",
            },
            {
              label: "macOS",
              href: "https://github.com/d221/vocaloid-rate/releases/download/v1.2.0/vocaloid-rate-macos.zip",
            },
          ],
        },
        {
          href: "https://github.com/d221/vocaloid-rate",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      copyright: `Copyright © ${new Date().getFullYear()} Vocaloid Rate, Inc. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
