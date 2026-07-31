/*
  两件事，都发生在 markdown 的 `![]()` 语法上，写文章的人不用碰 HTML。

  一、图注。

      ![替代文字](/img/2026/foo-800x600.webp "这句会变成图注")

  markdown 的第三个参数（title）本来只会变成鼠标悬停提示，基本没人看得到。
  这里把它抬出来做 <figcaption> —— 图下面那行小字。样式见
  styles/typography.css 的 figure / figcaption 两条。

  二、图表内联。

      ![替代文字](/charts/massratio.svg "图注")

  `/charts/*.svg` 不是真的 URL，是个约定：构建时从 src/assets/charts/ 把
  文件读进来，**把 SVG 直接铺进页面**，而不是留一个 <img src>。

  为什么非要内联：站有黑白两个主题（styles/theme.css 里 [data-theme]
  切 --background / --foreground / --accent 这一组变量）。<img> 里的图是
  一份独立文档，页面的 CSS 进不去，所以位图图表的底色只能写死 —— 写死成
  深色，浅色主题下就是页面里一块黑砖；反之亦然。内联进来以后 SVG 就是
  页面 DOM 的一部分，fill="var(--foreground)" 这种写法直接生效，主题一切
  图表跟着变，而且不用为两个主题各存一份文件。

  顺带的好处：图表是矢量，放大不糊、文字能选中能被搜索，体积也比 webp 小
  一个数量级（这几张 45–86 KB → 8–12 KB）。

  为什么不走 .mdx + Astro 的 SVG 组件导入（那是更常规的做法）：
  public/admin/config.yml 里文章集合写死了 `extension: md`，改成 .mdx
  这两篇就从后台消失了，而「后台改 → 提交 main → Cloudflare 构建」是发文
  主路径（见 .github/workflows/ci.yml 开头）。为了内联一张图切断主路径，
  不划算。

  边界：只认独占一段的图片 —— markdown 里 `![]()` 单独成行时生成的是
  <p><img></p>，这里把整个 <p> 换成 <figure>（<figure> 塞在 <p> 里是非法
  HTML，浏览器会把它拆开，版式当场散架）。行内混排的图片不碰，也不需要碰。
*/

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { fromHtml } from "hast-util-from-html";

/* 仓库路径里有空格，必须走 fileURLToPath —— .pathname 会给出 %20 编码过的
   字符串，readFileSync 找不到文件。upload-img.mjs 里踩过同一个坑。 */
const CHARTS_DIR = fileURLToPath(
  new URL("../../assets/charts/", import.meta.url)
);
const CHART_PREFIX = "/charts/";

type Node = {
  type: string;
  tagName?: string;
  value?: string;
  properties?: Record<string, unknown>;
  children?: Node[];
};

const isBlank = (n: Node) =>
  n.type === "text" && typeof n.value === "string" && n.value.trim() === "";

/** 这个 <p> 是不是「只装了一张图」。是的话返回那张图，否则 null。 */
function loneImage(node: Node): Node | null {
  if (node.type !== "element" || node.tagName !== "p") return null;
  const kids = (node.children ?? []).filter(c => !isBlank(c));
  if (kids.length !== 1) return null;
  const img = kids[0];
  return img?.type === "element" && img.tagName === "img" ? img : null;
}

function inlineChart(src: string, alt: string): Node {
  const name = src.slice(CHART_PREFIX.length);
  // 不许穿出 charts 目录 —— 文章内容不该能读到仓库里任意文件
  if (!/^[\w-]+\.svg$/.test(name)) {
    throw new Error(
      `[figures] 图表名不合法：${src}（只允许 /charts/<名字>.svg）`
    );
  }
  const file = CHARTS_DIR + name;
  if (!existsSync(file)) {
    throw new Error(`[figures] 找不到图表 ${file}（文章里引用的是 ${src}）`);
  }

  const tree = fromHtml(readFileSync(file, "utf8"), {
    fragment: true,
    space: "svg",
  }) as unknown as Node;
  const svg = (tree.children ?? []).find(
    n => n.type === "element" && n.tagName === "svg"
  );
  if (!svg) throw new Error(`[figures] ${file} 里没找到 <svg> 根元素`);

  const props = (svg.properties ??= {});
  /* 固定宽高会让它撑不满也缩不下去；留 viewBox，宽度交给容器。
     height:auto 必须显式写，否则 SVG 默认 150px 高，图会被压扁。 */
  delete props.width;
  delete props.height;
  props.style = "width:100%;height:auto;display:block";
  /* 图表是一张图，不是一堆图形 —— 屏幕阅读器应该念 alt，
     而不是逐个念里面几十个 <text>。 */
  props.role = "img";
  props["aria-label"] = alt;
  return svg;
}

export function rehypeFigures() {
  return (tree: Node) => {
    const walk = (node: Node) => {
      const kids = node.children;
      if (!kids) return;

      for (let i = 0; i < kids.length; i++) {
        const child = kids[i]!;
        const img = loneImage(child);

        if (img) {
          const p = img.properties ?? {};
          const src = typeof p.src === "string" ? p.src : "";
          const alt = typeof p.alt === "string" ? p.alt : "";
          const caption = typeof p.title === "string" ? p.title.trim() : "";
          // title 已经抬成图注了，留着只会多一个重复的悬停提示
          delete p.title;

          const content = src.startsWith(CHART_PREFIX)
            ? inlineChart(src, alt)
            : img;

          const figure: Node = {
            type: "element",
            tagName: "figure",
            properties: {},
            children: [content],
          };
          if (caption) {
            figure.children!.push({
              type: "element",
              tagName: "figcaption",
              properties: {},
              children: [{ type: "text", value: caption }],
            });
          }
          kids[i] = figure;
          continue;
        }

        walk(child);
      }
    };
    walk(tree);
  };
}
