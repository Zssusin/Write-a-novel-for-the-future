#!/usr/bin/env node
/*
  文章的跨文件校验，外加 uid 生成器。

  这里只管一件事：**zod 管不到的约束**。
  content.config.ts 的 schema 能保证「每篇文章自己是对的」——
  字段在不在、类型对不对、格式合不合。但它一次只看一个文件，
  所以「两篇文章之间的关系」得由这个脚本来看：

    · uid 不能重复            —— 撞了，评论和浏览量就会混到一起
    · 同系列里 part 不能重复   —— 撞了，连载目录出现两个「第 2 部分」

  还有一条例外，它是单文件约束但也放在这里：

    · ogImage 必须是绝对地址

  按理这该由 schema 管，但那个字段是 image().or(z.string())，
  相对路径能过 zod，然后死在 Astro 的图片解析里，报的是
  「[ImageNotFound] Could not find requested image」——
  看不出是 frontmatter 写错了。所以在这儿提前拦一道，给一句人话。

  另外还有几条**只提醒、不拦构建**的（走 notices，不走 problems）：

    · 正文里有被转义的星号     —— 后台改过加粗链接的痕迹
    · 封面不是 webp            —— 后台的自动转码没生效
    · slug 和文件名对不上      —— 后台改了「文件名」但地址没跟着变
    · 正文图没把尺寸写进文件名 —— 会让正文加载时跳版（CLS）

  这几条的共同点：发生在「后台改 → 提交 → Cloudflare 构建」这条主路径上，
  而 exit 1 在那条链上等于整站发不出去。为一处显示瑕疵付这个代价太贵，
  何况后三条在后台里根本修不了（要动 git 或者重传图片）。
  每一条要不要升级成 problem，各自的判断写在下面对应的位置。

  用法：
    npm run uid          生成一个新的 uid，贴进新文章的 frontmatter
    npm run check:posts  跑全部校验，构建前自动执行
*/
import { randomInt } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
// uid 的形状和文章目录跟 schema 共用一份，别在这里另抄一遍
import { IMG_SIZE_IN_NAME, POSTS_DIR, UID_PATTERN } from "./post-rules.mjs";

const LETTERS = "abcdefghijklmnopqrstuvwxyz";
const ALPHABET = `0123456789${LETTERS}`;

function newUid() {
  // randomInt 是无偏的，别用 Math.random() % 36
  return (
    LETTERS[randomInt(LETTERS.length)] +
    Array.from(
      { length: 7 },
      () => ALPHABET[randomInt(ALPHABET.length)]
    ).join("")
  );
}

/** 递归收集所有文章文件。`_` 开头的按 glob loader 的规则跳过。 */
function collectPosts(dir) {
  const found = [];
  for (const name of readdirSync(dir)) {
    if (name.startsWith("_")) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) found.push(...collectPosts(path));
    else if (/\.mdx?$/.test(name)) found.push(path);
  }
  return found;
}

/**
 * 切成 frontmatter 和正文两段。不做完整 YAML 解析 —— 够用且不引依赖。
 * 正文也要，因为下面有一条只能在正文里看的检查（被转义的星号）。
 */
function splitFrontmatter(path) {
  const match = readFileSync(path, "utf8").match(
    /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/
  );
  return match ? { frontmatter: match[1], body: match[2] } : null;
}

function readUid(frontmatter) {
  return frontmatter.match(/^uid:\s*["']?([^"'\s#]+)/m)?.[1] ?? null;
}

/**
 * 后台写下的「文件名」字段。手写的文章没有这一栏，返回 null。
 */
function readSlug(frontmatter) {
  return frontmatter.match(/^slug:\s*["']?([^"'\s#]+)/m)?.[1] ?? null;
}

/**
 * 空字符串和整个字段缺失都返回空串 —— 这两种都是「没填封面」，都合法。
 */
function readOgImage(frontmatter) {
  return frontmatter.match(/^ogImage:\s*["']?([^"'\s#]*)/m)?.[1] ?? "";
}

/*
  读 series 块。只认分行写法：

    series:
      name: 戴森球的工程学
      part: 2

  行内写法（series: { name: …, part: 2 }）YAML 合法，但这里不解析 ——
  与其写个半吊子的 YAML 解析器然后在某个引号上出错，不如只认一种形状、
  见到别的就明说。下面会把这种情况报成问题，不会悄悄跳过。
*/
function readSeries(frontmatter) {
  const lines = frontmatter.split(/\r?\n/);
  const start = lines.findIndex(line => /^series:/.test(line));
  if (start === -1) return null;
  /*
    `series: null`（或 ~、{}）当作「没有系列」。后台在这一栏留空时会写出
    这种形状，而不是把键整个省掉 —— 报成 malformed 的话，每一篇不带系列的
    后台文章都会卡在校验上。
  */
  if (/^series:\s*(null|~|\{\s*\})\s*$/i.test(lines[start])) return null;
  if (!/^series:\s*$/.test(lines[start])) return { malformed: true };

  const block = [];
  for (let i = start + 1; i < lines.length && /^\s+\S/.test(lines[i]); i++) {
    block.push(lines[i]);
  }
  const name = block
    .find(line => /^\s+name:/.test(line))
    ?.replace(/^\s+name:\s*/, "")
    .replace(/\s+#.*$/, "")
    .replace(/^["']|["']$/g, "")
    .trim();
  const part = block.find(line => /^\s+part:/.test(line))?.match(/(\d+)/)?.[1];

  if (!name || !part) return { malformed: true };
  return { name, part: Number(part) };
}

if (process.argv.includes("--new-uid")) {
  console.log(newUid());
  process.exit(0);
}

const problems = [];
const notices = []; // 不阻断构建，只是值得看一眼
const seenUids = new Map(); // uid -> 第一次出现的文件
const seriesIndex = new Map(); // 系列名 -> Map<part, 文件>

for (const path of collectPosts(POSTS_DIR).sort()) {
  const file = relative(POSTS_DIR, path);
  const parts = splitFrontmatter(path);

  if (parts === null) {
    problems.push(`${file}\n    没有 frontmatter。文件开头需要一段 --- 包起来的元数据。`);
    continue;
  }

  const { frontmatter, body } = parts;

  /*
    后台（Sveltia CMS）保存时会把「加粗包住链接」写坏，这是实测出来的：
    **[x](y)  →  \*\*[x](y)\*\*
    星号被转义成字面字符，读者看到的是一对光秃秃的 **。

    只报不拦。因为发文章的主路径是「后台改 → 提交 → Cloudflare 构建」，
    在那条链上 exit 1 意味着整篇文章直接不上线 —— 为一处显示瑕疵付这个代价
    太贵了。这里只在 npm run check:posts 的输出里提醒一句。
    详见 docs/后台发布.md 第 4 节。
  */
  if (/\\\*/.test(body)) {
    notices.push(
      `${file}\n    正文里有被转义的星号（\\*），加粗会显示成字面的 **。` +
        `\n    多半是后台改过「**[链接](...)**」这种写法。修：` +
        `\n      sed -i 's/\\\\\\*/*/g' ${POSTS_DIR}/${file}`
    );
  }

  const uid = readUid(frontmatter);
  if (!uid) {
    problems.push(`${file}\n    缺少 uid。加一行 uid: ${newUid()}`);
  } else if (!UID_PATTERN.test(uid)) {
    // 单独说清这一种：YAML 会把纯数字读成 number，schema 的报错看不出原因
    const reason = /^[0-9]/.test(uid)
      ? `uid "${uid}" 以数字开头。YAML 可能把它读成数字而不是字符串，首位请用字母。`
      : `uid "${uid}" 格式不对：8–40 位，首位小写字母，其余字母、数字或连字符。`;
    problems.push(`${file}\n    ${reason}\n    换成 ${newUid()}`);
  } else {
    const owner = seenUids.get(uid);
    if (owner) {
      problems.push(
        `${file}\n    uid "${uid}" 与 ${owner} 重复。` +
          `\n    两篇文章共用一个 uid 会让评论、浏览量混在一起。` +
          `\n    给这篇换一个：${newUid()}`
      );
    } else {
      seenUids.set(uid, file);
    }
  }

  /*
    后台那栏「文件名」只在**新建条目**的一刻决定文件叫什么，之后再改它，
    文件不会跟着改名 —— 而地址是从文件名推导出来的（src/utils/getPostPaths.ts）。
    所以改完的结果是：frontmatter 说自己叫 A，站上的地址还是 B，
    而且后台不会有任何提示。

    只报不拦，理由比转义星号那条还硬一层：这个问题**在后台里修不了**
    （改名要动 git）。发文章的主路径是「后台改 → 提交 → Cloudflare 构建」，
    在那条链上 exit 1 等于整站发不出去，而你还没法从后台把它修好。
  */
  const slug = readSlug(frontmatter);
  const basename = file.replace(/\.mdx?$/, "").split("/").pop();
  if (slug && slug !== basename) {
    notices.push(
      `${file}\n    frontmatter 里的 slug「${slug}」和文件名「${basename}」对不上。` +
        `\n    地址按文件名生成，所以这篇的网址仍然是 /posts/${basename}/。` +
        `\n    要真的改地址：git mv ${POSTS_DIR}/${file} ${POSTS_DIR}/${slug}.md` +
        `\n    （旧链接和收藏会全断，发出去之后一般就别改了。）` +
        `\n    不想改地址：把后台里的「文件名」一栏改回 ${basename}。`
    );
  }

  /*
    正文图能不能拿到 width/height。拿不到，图一加载完就把下面的正文顶一次（CLS）。

    尺寸这件事没人能替作者知道：/img/ 是 R2 上的远程地址，构建时既不下载
    也量不出来（为什么不下载，见 docs/图片工作流.md 第 6 节）。所以只能提醒。

    两种写法的补救路径不一样，分开报：

      ![](...)   —— src/utils/rehype/imageAttrs.ts 会照文件名里的 -宽x高 填。
                    所以这里检查的是文件名。
      <img>      —— 那个插件**看不到手写的 HTML**（.md 里是整块 raw 文本，
                    .mdx 里是 JSX 节点，都不是 hast 元素）。所以这里检查的是
                    标签上有没有真的写 width —— 文件名带尺寸也没用。

    只看 /img/ 开头的：public/images/ 里的图 Astro 自己会处理，外站的管不着。
  */
  const isRemoteImg = src => /^(\/img\/|https?:\/\/[^/]+\/img\/)/.test(src);

  const unsizedMarkdown = [
    ...new Set(
      [...body.matchAll(/!\[[^\]]*\]\(\s*([^)\s]+)/g)]
        .map(match => match[1])
        .filter(isRemoteImg)
    ),
  ].filter(src => !IMG_SIZE_IN_NAME.test(src.split(/[?#]/)[0]));

  if (unsizedMarkdown.length > 0) {
    notices.push(
      `${file}\n    有 ${unsizedMarkdown.length} 张正文图没把尺寸写进文件名：` +
        unsizedMarkdown.map(src => `\n      ${src}`).join("") +
        `\n    没有尺寸就填不出 width/height，图一加载完正文就往下跳一次（CLS）。` +
        `\n    量一下：file 图.webp  →  "…VP8 encoding, 1600x900…"` +
        `\n    然后按 <名字>-<宽>x<高>.webp 改名重传，正文里的地址跟着改。` +
        `\n    见 docs/图片工作流.md 第 3 节。`
    );
  }

  const unsizedHtml = [...body.matchAll(/<img\b[^>]*>/g)]
    .map(match => match[0])
    .filter(tag => {
      const src = tag.match(/\bsrc=["']([^"']+)["']/)?.[1] ?? "";
      return isRemoteImg(src) && !/\bwidth\s*=/.test(tag);
    });

  if (unsizedHtml.length > 0) {
    notices.push(
      `${file}\n    有 ${unsizedHtml.length} 个手写的 <img> 没有 width/height：` +
        unsizedHtml.map(tag => `\n      ${tag}`).join("") +
        `\n    手写的标签构建时不会被加工（插件只认 markdown 的 ![](...) 写法），` +
        `\n    所以尺寸和 loading="lazy" 都得自己写全，文件名带尺寸对它没用。`
    );
  }

  const ogImage = readOgImage(frontmatter);
  if (ogImage && !/^https?:\/\//.test(ogImage)) {
    problems.push(
      `${file}\n    ogImage "${ogImage}" 不是绝对地址。` +
        `\n    这一栏必须写完整的 http(s) 地址，站内相对路径会让构建失败：` +
        `\n      [ImageNotFound] Could not find requested image \`${ogImage}\`` +
        `\n    改成 https://clarkebelt.org${ogImage.startsWith("/") ? "" : "/"}${ogImage}` +
        `\n    （后台里从 R2 媒体库选图会自动写成绝对地址，不用手打。）`
    );
  } else if (ogImage && !/\.webp(\?|$)/i.test(ogImage)) {
    /*
      不阻断构建 —— 非 webp 的封面能用，只是白白多下载几倍字节。
      但它同时是个信号：后台上传本该自动转 webp（config.yml 里的
      transformations），出现非 webp 说明那段配置又没生效了。
    */
    notices.push(
      `${file}\n    封面 ${ogImage.split("/").pop()} 不是 webp。` +
        `\n    后台上传本应自动转 webp；出现别的格式，多半是 config.yml 里` +
        `\n    media_libraries.default.config.transformations 没被读到。` +
        `\n    见 docs/图片工作流.md 2.5 节。`
    );
  }

  const series = readSeries(frontmatter);
  if (series?.malformed) {
    problems.push(
      `${file}\n    series 读不出来。请写成分行的形状：` +
        `\n      series:\n        name: 系列名\n        part: 2`
    );
  } else if (series) {
    const parts = seriesIndex.get(series.name) ?? new Map();
    const owner = parts.get(series.part);
    if (owner) {
      problems.push(
        `${file}\n    系列「${series.name}」的第 ${series.part} 部分与 ${owner} 重复。` +
          `\n    同一个系列里 part 必须唯一，否则目录里会出现两个「第 ${series.part} 部分」。`
      );
    } else {
      parts.set(series.part, file);
      seriesIndex.set(series.name, parts);
    }
  }
}

if (problems.length > 0) {
  // 一次性刷几百条没人看得下去，先修前面这些通常就顺带修完了
  const SHOWN = 15;
  console.error(`\n✗ 文章校验失败（${problems.length} 处）：\n`);
  for (const problem of problems.slice(0, SHOWN)) console.error(`  ${problem}\n`);
  if (problems.length > SHOWN) {
    console.error(`  ……还有 ${problems.length - SHOWN} 处，修完上面这些再跑一次。\n`);
  }
  process.exit(1);
}

console.log(`✓ 文章校验通过：${seenUids.size} 篇，uid 无重复`);

for (const notice of notices) console.log(`\n  ⚠ ${notice}`);
if (notices.length > 0) console.log("");

/*
  把系列清单打出来。名字是手打的中文，「戴森球的工程学」和「戴森球工程学」
  在机器看来是两个系列，脚本没法判断哪个是笔误 —— 但列出来你一眼就看得见：
  凭空多出一个只有一部分的系列，基本就是打错了字。
*/
for (const [name, parts] of [...seriesIndex].sort()) {
  const numbers = [...parts.keys()].sort((a, b) => a - b).join("、");
  console.log(`  系列「${name}」：第 ${numbers} 部分`);
}
