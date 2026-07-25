import { defineAstroPaperConfig } from "./src/types/config";

export default defineAstroPaperConfig({
  site: {
    // TODO: change to your real domain before deploying (used for canonical URLs, OG images, RSS).
    url: "https://example.com/",
    title: "科幻工具站",
    description:
      "硬科幻爱好者的笔记：现实科技解读、原创故事、创作工具箱与书目推荐。",
    author: "chen", // TODO: your name or pen name
    profile: "https://example.com/",
    ogImage: "default-og.jpg",
    lang: "zh",
    timezone: "Asia/Shanghai",
    dir: "ltr",
  },
  posts: {
    perPage: 4,
    perIndex: 4,
    scheduledPostMargin: 15 * 60 * 1000,
  },
  features: {
    lightAndDarkMode: true,
    dynamicOgImage: true,
    showArchives: true,
    showBackButton: true,
    // "Edit page" link pointed at the theme author's repo — off until you wire up your own.
    editPost: {
      enabled: false,
    },
    search: "pagefind",
  },
  // TODO: add your own links (github / mail / etc.). Empty for now.
  socials: [],
  shareLinks: [
    { name: "x", url: "https://x.com/intent/post?url=" },
    { name: "telegram", url: "https://t.me/share/url?url=" },
    { name: "mail", url: "mailto:?subject=See%20this%20post&body=" },
  ],
});
