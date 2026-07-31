#!/usr/bin/env node
/*
  给封面图生成列表用的小尺寸档位。

  为什么要这一步：ogImage 那一栏同时兼着社交预览图，尺寸按 OG 卡片来
  （1200x630 那种）。但同一张图在文章列表里只是一枚缩略图 —— 桌面端
  176x112，被 object-cover 裁完实际只用到约 213 CSS px 宽。实测首页的
  LCP 元素就是它：原图 134,516 B，而 440 那档只要 14,530 B。

  档位只出 440 和 720，不出 1080：手机上这张图是满宽显示，720 对一个
  390px 的框是 1.85×，而它本来就要被 object-cover 裁掉一块，再翻一倍
  字节买那点锐度不划算（实测 1080 档 78,056 B，比原图只省 42%）。

  ⚠️ 文件名必须是 `名字-宽x高.webp`。Card.astro 的 srcset 是靠这个后缀
  **推**出来的（构建时没法枚举 R2 里有什么），这里的命名和那边的推导是
  同一套算法，改一边就要改另一边。npm run check:posts 会挨个 HEAD 一遍。

  用法：
      node scripts/make-thumbs.mjs ../图片待上传/foo-1200x630.webp
      node scripts/make-thumbs.mjs https://clarkebelt.org/img/2026/foo-1200x630.webp
      node scripts/make-thumbs.mjs --out /tmp/t <图…>

  收远程地址是给**补做**用的：原图传上去之后本地往往就不留底了，
  与其让人先手动下回来，不如脚本自己取。

  生成完把打印出来的文件喂给 upload-img.mjs 即可。
*/

import sharp from "sharp";
import { writeFile, stat, mkdir } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

const WIDTHS = [440, 720];
const QUALITY = 82;

const args = process.argv.slice(2);
let outDir = null;
const inputs = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--out") outDir = args[++i];
  else inputs.push(args[i]);
}

if (inputs.length === 0) {
  console.error("用法：node scripts/make-thumbs.mjs [--out 目录] <图片或地址…>");
  process.exit(1);
}

/* 远程图先落到本地再交给 sharp —— sharp 只吃 Buffer 或路径，不认 URL。 */
async function load(input) {
  if (/^https?:\/\//.test(input)) {
    const res = await fetch(input);
    if (!res.ok) throw new Error(`取不到（HTTP ${res.status}）`);
    return {
      buf: Buffer.from(await res.arrayBuffer()),
      name: basename(new URL(input).pathname),
      dir: outDir ?? process.cwd(),
    };
  }
  const path = resolve(input);
  await stat(path); // 不存在就在这里抛，错误信息比 sharp 的清楚
  return { buf: path, name: basename(path), dir: outDir ?? dirname(path) };
}

const made = [];
let failed = 0;

for (const input of inputs) {
  try {
    const { buf, name, dir } = await load(input);
    const parts = name.match(/^(.*)-(\d+)x(\d+)(\.[a-z0-9]+)$/i);
    if (!parts) {
      console.error(`✗ ${name}\n  文件名没带 -宽x高，推不出档位。先按约定改名。`);
      failed++;
      continue;
    }

    const meta = await sharp(buf).metadata();
    const [, base, declaredW, , ext] = parts;
    /*
      文件名里写的宽高和真实宽高对不上时以**真实**的为准，但要说一句 ——
      名字对不上通常意味着这张图被人改过尺寸却没改名，正文图那边的
      rehype 插件也靠这个名字填 width/height，会一起错。
    */
    if (Number(declaredW) !== meta.width) {
      console.warn(
        `  ⚠ ${name} 名字写着 ${declaredW} 宽，实际 ${meta.width}。按实际算，但建议改名。`
      );
    }

    await mkdir(dir, { recursive: true });
    const orig = meta.size ?? (typeof buf === "string" ? (await stat(buf)).size : buf.length);
    console.log(`\n${name}  ${meta.width}x${meta.height}  ${orig.toLocaleString()} B`);

    for (const w of WIDTHS) {
      if (w >= meta.width) {
        console.log(`  ${w}   跳过：原图只有 ${meta.width} 宽`);
        continue;
      }
      const h = Math.round((meta.height * w) / meta.width);
      const out = join(dir, `${base}-${w}x${h}${ext}`);
      const data = await sharp(buf).resize(w).webp({ quality: QUALITY }).toBuffer();
      await writeFile(out, data);
      made.push(out);
      console.log(
        `  ${w}   ${basename(out)}  ${data.length.toLocaleString()} B  = 原图的 ${((data.length / orig) * 100).toFixed(1)}%`
      );
    }
  } catch (e) {
    console.error(`✗ ${input}\n  ${e.message}`);
    failed++;
  }
}

if (made.length > 0) {
  console.log(`\n生成 ${made.length} 个。上传：`);
  console.log(`  node scripts/upload-img.mjs ${made.map(p => `"${p}"`).join(" ")}`);
}

process.exit(failed ? 1 : 0);
