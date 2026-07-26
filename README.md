# clarkebelt

硬科幻爱好者的笔记站：现实科技解读、原创故事、创作工具箱、书目推荐。

线上地址：<https://clarkebelt.org>

## 它是怎么跑起来的

一个纯静态站。文章是仓库里的 Markdown，推进 `main` 之后 Cloudflare 构建、
把 `dist/` 整个当 CDN 发出去。

```
写作 ──► /admin/（后台，浏览器里直接调 GitHub API）
          │
          ├─ 或者直接改 src/content/posts/*.md
          ▼
       commit 到 main
          │
          ▼
   Cloudflare 构建（npm run build）
          │
          ▼
   Workers 静态资源层 ──────────────► 文章、CSS、Pagefind 索引……
          └─ 只有 /img/* 例外 ──► worker/index.js ──► R2 桶（图片）
```

全链路没有数据库，也没有需要盯着的服务器进程。唯一那段服务端代码是
[`worker/index.js`](worker/index.js)（不到 40 行有效代码），存在的理由只有一个：
让文章里的图片地址是 `/img/xxx`，而不是写死的 `pub-xxxx.r2.dev`——
换域名、换桶、哪天离开 Cloudflare，正文一个字都不用动。

## 上手

需要 Node ≥ 22.12（用 nvm 装）。

```bash
npm install
npm run dev      # http://localhost:4321
```

| 命令                  | 作用                                               |
| :-------------------- | :------------------------------------------------- |
| `npm run dev`         | 本地开发服务器                                     |
| `npm run build`       | 校验 + 类型检查 + 构建 + Pagefind 建索引           |
| `npm run preview`     | 本地预览构建产物                                   |
| `npm run check:posts` | 只跑文章校验（uid 是否重复、系列 part 是否撞车……） |
| `npm run uid`         | 生成一个新的 uid，贴进新文章的 frontmatter         |
| `npm run lint`        | ESLint                                             |
| `npm run format`      | Prettier 格式化                                    |

`npm run build` 是唯一一条构建路径——CI 和 Cloudflare 跑的都是它。
本地过了，线上基本就不会挂。

## 写一篇文章

新文章放 `src/content/posts/<英文短横线名>.md`，文件名就是网址。
frontmatter 的字段和约束定义在 [`src/content.config.ts`](src/content.config.ts)，
跨文件的约束（uid 不重复、同系列 part 不重复）由
[`scripts/check-posts.mjs`](scripts/check-posts.mjs) 在构建前检查。

具体工序见 `docs/`：

| 文档                             | 讲什么                                  |
| :------------------------------- | :-------------------------------------- |
| [后台发布](docs/后台发布.md)     | `/admin/` 怎么登录、怎么发、有哪些坑    |
| [图片工作流](docs/图片工作流.md) | R2 建桶、上传、在文章里引用、封面图要求 |
| [翻译工序](docs/翻译工序.md)     | 授权、分篇、译文与注解的写法            |
| [站标](docs/站标.md)             | favicon 的唯一源文件与重新生成步骤      |

## 关于主题

本站基于 [AstroPaper](https://github.com/satnaing/astro-paper) v6.1.0
（作者 [Sat Naing](https://satnaing.dev)，MIT 许可，见 [LICENSE](LICENSE)）。

**这是一次性快照，不跟随上游。** 主题代码是复制进来的，之后按本站需要改过不少
（首页、归档、OG 图生成、字体加载、`src/styles/glass.css` 那套材质、系列导航与
译文出处组件都是自己写的），已经没有机械化的升级路径。上游发新版时，只能人工
挑补丁——所以别指望 `git merge`，也别为了「方便升级」把改动改回去。

## 技术栈

[Astro](https://astro.build/) · [TypeScript](https://www.typescriptlang.org/) ·
[TailwindCSS](https://tailwindcss.com/) · [Pagefind](https://pagefind.app/)（静态搜索） ·
[Sveltia CMS](https://github.com/sveltia/sveltia-cms)（后台） ·
[Satori](https://github.com/vercel/satori) + [Sharp](https://sharp.pixelplumbing.com/)（动态 OG 图） ·
[Cloudflare Workers](https://workers.cloudflare.com/)（部署） ·
[Cloudflare R2](https://developers.cloudflare.com/r2/)（图片）
