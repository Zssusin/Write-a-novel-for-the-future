/*
  把项目根目录的 `_headers` 复制进 dist/。

  ── 为什么需要一个集成，而不是直接把文件放进 public/ ──

  按 Cloudflare 的约定，`_headers` 就该放在 public/ 里跟着构建产物走。
  **但在这套工具链上放不了**：Astro 7 的打包器是 rolldown，它会把 public/ 里
  **没有扩展名**的文件当成 JS 模块去解析。`_headers` 的第一行是

      # Cloudflare 静态资源的响应头。…

  而 `#` 后面跟空格在 JS 里是非法的（`#` 只能起私有字段名），于是整个构建
  当场挂掉：

      [PARSE_ERROR] Invalid Character ` `
         ╭─[ public/_headers:1:2 ]

  实测过三种情况，结论很明确：换成 `_headers.txt` 能构建（说明是扩展名的事，
  不是文件名的事）；同名但内容碰巧是合法 JS 的也能构建（所以这个坑是**静默**的
  —— 改一行注释就可能突然炸）；`.txt` 那份又不能用，Cloudflare 只认
  `_headers` 这个准确的名字。

  所以只剩两条路：把文件写成合法的 JS（意味着不能写 `#` 注释，而这份文件
  一多半是解释「为什么这么缓存」的注释），或者绕开 Vite 自己复制。选后者。

  ── 为什么用 astro:build:done ──

  这个钩子在产物全部落盘之后跑，复制进去不会被后续步骤清掉。
  写在这里而不是塞进 package.json 的 `npm run build` 那串 `&&` 里，是因为
  直接跑 `astro build` 的人（包括 Cloudflare 面板上如果哪天改了构建命令）
  也该拿到这个文件 —— 缓存策略不该依赖某一条 shell 命令有没有被记得写上。
*/

import type { AstroIntegration } from "astro";
import { copyFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

/* 仓库路径里有空格，必须走 fileURLToPath —— .pathname 给的是 %20 编码过的
   字符串，fs 找不到文件。utils/rehype/figures.ts 和 scripts/upload-img.mjs
   里踩过同一个坑。 */
const SOURCE = fileURLToPath(new URL("../../_headers", import.meta.url));

export function cacheHeaders(): AstroIntegration {
  return {
    name: "cache-headers",
    hooks: {
      "astro:build:done": async ({ dir, logger }) => {
        const target = fileURLToPath(new URL("_headers", dir));
        /*
          故意不 try/catch：源文件不在了就该让构建响。静默跳过的话，站会带着
          「全站 max-age=0」上线，而没有任何人会注意到 —— 那正是加这个文件
          要解决的问题。
        */
        await copyFile(SOURCE, target);
        logger.info("`_headers` copied to dist/");
      },
    },
  };
}
