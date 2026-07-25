import { defineAstroPaperConfig } from "./src/types/config";

export default defineAstroPaperConfig({
  site: {
    /*
      canonical 链接、OG 图地址、RSS、sitemap、robots.txt 里的地址全从这里拼。
      填错的后果是安静的：站能打开，但搜索引擎照 canonical 认为你的内容在别处。

      再换域名的话改这一行 —— 同时改 public/admin/config.yml 里的 site_url。
      两处必须一起改：只改一个，站照样能开，但两边说的不是同一个地址。

      旧的 write-a-novel-for-the-future.chen202028.workers.dev 还在服务，
      而且发的也是这份产物 —— 也就是说它会带着指向 clarkebelt.org 的 canonical，
      搜索引擎会把权重并到这边来。这是想要的行为，不用去关掉它。
    */
    url: "https://clarkebelt.org/",
    /*
      站名 = 域名。这个字符串会出现在 <title>、og:site_name、页头字标、
      页脚版权行、RSS 频道名，以及 og.png 那张分享图上。改一处，全站跟着走。

      故意全小写、故意是拉丁字母：页头字标用 Michroma 渲染（--font-display），
      而 Michroma 的 unicode-range 只覆盖拉丁，中文会回落成系统字体。
      站名要是中文，那套字体就等于白加载。
    */
    title: "clarkebelt",
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
