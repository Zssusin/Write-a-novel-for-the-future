#!/usr/bin/env node
/*
  把图片传进 R2 的 image 桶，不用交互式 `wrangler login`。

  为什么要这个脚本，而不是直接敲 docs/图片工作流.md 第 2 节那条命令：

  1. `wrangler login` 是 OAuth 浏览器流程，脚本里/代理里都跑不了。
     wrangler 认 CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID 这两个环境变量，
     配上就能非交互上传 —— 但它**不会自己读 .env**，得有人喂给它。这里喂。

  2. 对象名要带年份目录（2026/foo.webp），手敲容易和文件名写岔。这里从
     文件名 + --year 推。

  3. 顺手把 docs 里那两条约定检查一遍：非 webp 要提醒（远程图 Astro 不优化），
     正文图文件名要带 -宽x高（rehype 插件靠它填 width/height，不然正文跳版）。

  用法：
      node scripts/upload-img.mjs ../图片待上传/*.webp
      node scripts/upload-img.mjs --year 2027 foo.webp

  一次性设置：把下面两行写进 scifi-blog/.env（.gitignore 里已经有 .env）
      CLOUDFLARE_ACCOUNT_ID=4496da3ff5894affc28fd48211aff811
      CLOUDFLARE_API_TOKEN=<在 Dashboard → 右上角头像 → API Tokens 建，
                            权限选 Account / Workers R2 Storage / Edit>
*/

import { execFileSync } from "node:child_process";
import { readFileSync, existsSync, statSync } from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const BUCKET = "image";
const SITE = "https://clarkebelt.org";
/* 必须走 fileURLToPath，不能用 .pathname —— 仓库路径里有空格，
   .pathname 给的是 %20 编码过的字符串，existsSync 永远找不到这个文件。 */
const ENV_FILE = fileURLToPath(new URL("../.env", import.meta.url));

/* .env 是 KEY=VALUE 的行集合，不做 shell 展开 —— 值里有 # 也原样保留，
   token 里出现 # 并不稀奇，按注释切会把它截断。 */
function loadEnv(path) {
  if (!existsSync(path)) return {};
  const out = {};
  for (const raw of readFileSync(path, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    out[line.slice(0, eq).trim()] = line
      .slice(eq + 1)
      .trim()
      .replace(/^["']|["']$/g, "");
  }
  return out;
}

const args = process.argv.slice(2);
let year = String(new Date().getFullYear());
const files = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--year") year = args[++i];
  else files.push(args[i]);
}

if (files.length === 0) {
  console.error("用法：node scripts/upload-img.mjs [--year 2026] <图片…>");
  process.exit(1);
}

const env = { ...loadEnv(ENV_FILE), ...process.env };
const missing = ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"].filter(
  k => !env[k]
);
if (missing.length) {
  console.error(`缺少 ${missing.join("、")}。`);
  console.error(`把它们写进 ${ENV_FILE}，建 token 的步骤见本文件开头的注释。`);
  process.exit(1);
}

let failed = 0;
for (const f of files) {
  const path = resolve(f);
  if (!existsSync(path) || !statSync(path).isFile()) {
    console.error(`✗ ${f} —— 文件不存在`);
    failed++;
    continue;
  }

  const name = basename(path);
  const key = `${year}/${name}`;

  if (!name.endsWith(".webp")) {
    console.warn(`  ⚠ ${name} 不是 webp。远程图 Astro 不会优化，先压一遍。`);
  }
  if (!/-\d+x\d+\.\w+$/.test(name)) {
    console.warn(
      `  ⚠ ${name} 文件名没带 -宽x高。正文图会拿不到 width/height（封面图无所谓）。`
    );
  }

  try {
    /* --remote 必须显式写：wrangler 4 的 r2 object 命令不加就可能落到本地
       模拟存储里，命令成功、桶里什么都没有。 */
    execFileSync(
      "npx",
      ["wrangler", "r2", "object", "put", `${BUCKET}/${key}`, "--file", path, "--remote"],
      { env, stdio: ["ignore", "pipe", "pipe"] }
    );
    console.log(`✓ ${name}\n  ${SITE}/img/${key}`);
  } catch (e) {
    /* wrangler 的 stderr 里夹着大量空行和 ANSI 码，直接 slice(-3) 经常
       只截到空行。滤掉空行再取，否则报错看起来像什么都没说。 */
    const msg = (e.stderr?.toString() || e.message)
      .replace(/\x1b\[[0-9;]*m/g, "")
      .split("\n")
      .map(l => l.trim())
      .filter(Boolean)
      .slice(-3);
    console.error(`✗ ${name}\n  ${msg.join("\n  ") || "(wrangler 未输出错误信息)"}`);
    failed++;
  }
}

process.exit(failed ? 1 : 0);
