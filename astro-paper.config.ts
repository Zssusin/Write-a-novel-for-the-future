import { defineAstroPaperConfig } from "./src/types/config";

export default defineAstroPaperConfig({
  site: {
    /*
      canonical 链接、OG 图地址、RSS、sitemap、robots.txt 里的地址全从这里拼。
      填错的后果是安静的：站能打开，但搜索引擎照 canonical 认为你的内容在别处。

      以后绑了自己的域名，改这一行 —— 同时改 public/admin/config.yml 里的 site_url。
      改域名那次记得留意：换了地址等于换了一套 URL，旧地址的收录会重新算。
    */
    url: "https://write-a-novel-for-the-future.chen202028.workers.dev/",
    title: "科幻工具站",
    description:
      "硬科幻爱好者的笔记：现实科技解读、原创故事、创作工具箱与书目推荐。",
    author: "chen", // TODO: your name or pen name
    /*
      作者主页，会写进文章的结构化数据（PostLayout.astro 里那段 JSON-LD）。
      填你自己的地址：GitHub、别的社交页，随便什么能代表你的页面。
      留空是有意的 —— 代码里是 `site.profile && {...}`，空字符串就整个不声明，
      比填一个不属于你的地址干净。
    */
    profile: "",
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
