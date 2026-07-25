#!/usr/bin/env node
/*
  文章的跨文件校验，外加 uid 生成器。

  这里只管一件事：**zod 管不到的约束**。
  content.config.ts 的 schema 能保证「每篇文章自己是对的」——
  字段在不在、类型对不对、格式合不合。但它一次只看一个文件，
  所以「两篇文章之间的关系」得由这个脚本来看：

    · uid 不能重复            —— 撞了，评论和浏览量就会混到一起
    · 同系列里 part 不能重复   —— 撞了，连载目录出现两个「第 2 部分」

  用法：
    npm run uid          生成一个新的 uid，贴进新文章的 frontmatter
    npm run check:posts  跑全部校验，构建前自动执行
*/
import { randomInt } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

// 与 content.config.ts 里的 BLOG_PATH 保持一致
const POSTS_DIR = "src/content/posts";
const LETTERS = "abcdefghijklmnopqrstuvwxyz";
const ALPHABET = `0123456789${LETTERS}`;
/*
  首字符必须是字母。这不是审美问题 ——
  全是数字的 uid（比如 00000000）会被 YAML 解析成「数字」而不是字符串，
  schema 报的是 "Expected string, received number"，排查起来很费劲。
  让首位永远是字母，这种情况按构造就不可能出现。
  熵还是够：26 × 36^7 ≈ 2×10^12。

  长度收到 8–40 位、允许大写和连字符，是为了同时接受后台生成的那种 ——
  浏览器里跑不了 npm，Sveltia CMS 的 uuid 组件只会吐 UUID 或 26 位 Base32。
  两种来源都是「创建时生成一次，之后不再变」，对 uid 来说这才是关键。
*/
const UID_PATTERN = /^[a-z][0-9a-zA-Z-]{7,39}$/;

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

/** 只截开头那段 frontmatter，不做完整 YAML 解析 —— 够用且不引依赖。 */
function readFrontmatter(path) {
  return (
    readFileSync(path, "utf8").match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1] ?? null
  );
}

function readUid(frontmatter) {
  return frontmatter.match(/^uid:\s*["']?([^"'\s#]+)/m)?.[1] ?? null;
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
const seenUids = new Map(); // uid -> 第一次出现的文件
const seriesIndex = new Map(); // 系列名 -> Map<part, 文件>

for (const path of collectPosts(POSTS_DIR).sort()) {
  const file = relative(POSTS_DIR, path);
  const frontmatter = readFrontmatter(path);

  if (frontmatter === null) {
    problems.push(`${file}\n    没有 frontmatter。文件开头需要一段 --- 包起来的元数据。`);
    continue;
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
/*
  把系列清单打出来。名字是手打的中文，「戴森球的工程学」和「戴森球工程学」
  在机器看来是两个系列，脚本没法判断哪个是笔误 —— 但列出来你一眼就看得见：
  凭空多出一个只有一部分的系列，基本就是打错了字。
*/
for (const [name, parts] of [...seriesIndex].sort()) {
  const numbers = [...parts.keys()].sort((a, b) => a - b).join("、");
  console.log(`  系列「${name}」：第 ${numbers} 部分`);
}
