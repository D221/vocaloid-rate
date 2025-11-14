import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";
import apisidebar from "../docs/api/sidebar";

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    "intro",
    "features",
    "installation-end-users",
    "installation-docker",
    "development-setup",
    "production-release",
    "apis-used",
    {
      type: "category",
      label: "API Reference",
      link: {
        type: "generated-index",
        title: "API Reference",
        slug: "/category/api-reference",
      },
      items: apisidebar,
    },
    "database-schema",
  ],
};

export default sidebars;
