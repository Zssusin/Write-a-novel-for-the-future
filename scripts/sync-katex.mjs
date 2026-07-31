#!/usr/bin/env node
/*
  把 KaTeX 的样式表和字体从 node_modules 复制到 public/katex/。

  ── 为什么要复制，而不是 import ──

  常规做法是在某个组件里 `import "katex/dist/katex.min.css"`，让 Astro 打包。
  这里不行，原因和 giscus 那次一样：**Astro 是按「组件有没有被导入」收集
  资源的，不是按「有没有被渲染」**。全站文章共用 pages/posts/[...slug]/
  index.astro 一个文件，只要那里出现过这条 import，哪怕包在
  `{hasMath && ...}` 里，KaTeX 的 CSS 也会进每一个文章页的样式包。

  而这份 CSS 压缩后 3.6 KB —— 站里主样式表 gzip 后一共才 11.7 KB，
  给一篇公式都没有的文章加三分之一的样式体积，不划算。

  放进 public/ 之后就是一个普通静态文件，由 PostLayout 在
  **确实含公式的那些页面**上单独 <link> 进来（hasMath 由
  utils/remark/mathFlag.ts 在构建时标记）。dev 和构建两边行为一致。

  ── 为什么只要 woff2 ──

  KaTeX 每种字体都提供 woff2 / woff / ttf 三份，共 60 个文件、1.2 MB。
  但 CSS 里三份是写在**同一条 src 里**并带 format() 提示的，浏览器认准
  第一个支持的格式（woff2）就不会再去要后两个。所以 woff / ttf 从来
  不会被请求，复制过去就是白占仓库 900 KB。
  （这和 astro.config.ts 里给自有字体只留 woff2 的判断是同一条。）

  样式表本身**原样复制、一个字节不改**。改写它去掉 woff/ttf 那两行也行，
  但那样 public/ 里就多了一个「派生且和上游不一致」的文件，升级 KaTeX 时
  很容易忘记重做。原样复制的话，这个脚本重跑一遍就永远是对的。

  用法：
    node scripts/sync-katex.mjs           复制（升级 katex 之后跑一次）
    node scripts/sync-katex.mjs --check   只校验版本是否和 package.json 一致
*/
import { copyFileSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/* 仓库路径里有空格，必须走 fileURLToPath —— .pathname 给的是 %20 编码过的
   字符串，fs 找不到文件。upload-img.mjs 和 rehype/figures.ts 都踩过。 */
const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const SRC = join(ROOT, "node_modules", "katex", "dist");
const DEST = join(ROOT, "public", "katex");
const STAMP = join(DEST, "VERSION");

const installed = JSON.parse(
  readFileSync(join(ROOT, "node_modules", "katex", "package.json"), "utf8")
).version;

const checkOnly = process.argv.includes("--check");

if (checkOnly) {
  /*
    构建前的漂移检查。升级了 katex 却忘了重跑这个脚本时，public/ 里躺的
    还是旧版样式表 —— 新版 KaTeX 生成的 class 名对不上旧 CSS，公式会渲染成
    一堆散落的字母，而且**构建不会报任何错**。所以这里主动拦一道。
  */
  const stamped = existsSync(STAMP) ? readFileSync(STAMP, "utf8").trim() : null;
  if (stamped !== installed) {
    console.error(
      `✗ public/katex 是 ${stamped ?? "缺失"}，安装的 katex 是 ${installed}\n` +
        `  跑一下：node scripts/sync-katex.mjs`
    );
    process.exit(1);
  }
  console.log(`✓ public/katex 与 katex ${installed} 一致`);
  process.exit(0);
}

rmSync(DEST, { recursive: true, force: true });
mkdirSync(join(DEST, "fonts"), { recursive: true });

copyFileSync(join(SRC, "katex.min.css"), join(DEST, "katex.min.css"));

const fonts = readdirSync(join(SRC, "fonts")).filter(f => f.endsWith(".woff2"));
for (const font of fonts) {
  copyFileSync(join(SRC, "fonts", font), join(DEST, "fonts", font));
}

writeFileSync(STAMP, `${installed}\n`);

console.log(`✓ KaTeX ${installed} → public/katex/（1 个样式表 + ${fonts.length} 个 woff2）`);
