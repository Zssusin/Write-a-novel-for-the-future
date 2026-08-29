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

  三、图号。

  「图 1」「图 2」…… 原来是 CSS 计数器画的（typography.css 里
  figcaption::before + counter(fig)）。挪到这里，是因为 CSS 生成的内容
  **只存在于渲染结果里**：DOM 里没有这个数，页面上也没有可以指过去的锚点。
  于是三件事都做不了 ——

    · 侧栏列不出「图表目录」（列出来也无从跳转）
    · 正文里写不了「见图 3」并自动链过去
    · 读者复制一段图注，编号不会跟着走

  在这里编号，figure 拿到 id="fig-N"，图注里多一个 <span class="fig-label">，
  三件事同时成立。代价是 CSS 少了一条自动性：以后手写的 <figure> 不会
  自动得到编号 —— 但这个站的图全部来自 markdown 的 `![]()`，都经过这里。

  编号只给**写了图注的图**，和原来 CSS 里 counter-increment 挂在 figcaption
  上是同一条规则：没有说明文字的图不占号。

  编号计数器必须建在**转换函数内部**：unified 的插件函数只在搭管道时调用
  一次，返回的 transformer 被所有文章复用。计数器写在外层的话，第二篇文章
  的第一张图会从上一篇的号往下接。
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

/*
  和 readingTime.ts / mathFlag.ts 走同一条通道：把构建期算出来的东西写进
  file.data.astro.frontmatter，页面用 `await render(post)` 的
  remarkPluginFrontmatter 取。名字里带 remark 但 rehype 插件写的一样收得到 ——
  两边共用的是同一个 vfile，Astro 在整条管道跑完之后才把它读出来。
*/
type FileWithFrontmatter = {
  data?: {
    astro?: {
      frontmatter?: Record<string, unknown>;
    };
  };
};

/** 一张图在「图表目录」里的一条。 */
export type FigureEntry = {
  /** 锚点 id，形如 fig-3 */
  id: string;
  /**
   * 现成的编号文字，如「图 3」。
   *
   * 存整串而不是存数字 + 让侧栏自己拼：拼的话「图」字就有了第三个出处
   * （这里、remark/directives.ts、侧栏组件），而它们必须永远一致 ——
   * 图注上写「图 3」、目录里写「Fig 3」是不能接受的。存整串，
   * 图注和目录读的就是同一个值。
   */
  label: string;
  /** 图注原文（不含编号） */
  caption: string;
};

/*
  「图」这个字硬编码在这里。原来它硬编码在 CSS 的 content 里（那处连
  i18n 的可能性都没有），挪过来至少变成了一个能改的常量。站是中文单语
  （astro.config.ts 的 i18n.locales 只有 zh），真加第二种语言时，这里和
  remark/directives.ts 里 :fig 那条要一起按文章语言取。
*/
export const FIG_WORD = "图";

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

/*
  校验正文里的图号引用。

  认的是**指向图锚点的链接**，不看是谁写的 —— :fig[3] 生成的，和作者手写的
  [见图 3](#fig-3)，都得指得中。判断放在这里而不是 remark 阶段：图号是这个
  插件编的，remark 跑的时候还不知道这篇有几张图。

  指不中就**让构建失败**。整个文件的其他地方（未登记的指令、没带尺寸的远程图）
  都是静默降级，这一处例外，因为后果不一样：一个断掉的「见图 5」不是少了点
  样式，是把读者指向一张不存在的图 —— 那是错的信息，不是缺的信息。
  和 check-posts.mjs 对 uid 的态度一致。
*/
function checkFigureRefs(tree: Node, total: number): void {
  const walk = (node: Node) => {
    if (node.type === "element" && node.tagName === "a") {
      const href = node.properties?.href;
      const m = typeof href === "string" ? /^#fig-(\d+)$/.exec(href) : null;
      if (m) {
        const n = Number(m[1]);
        if (n < 1 || n > total) {
          throw new Error(
            `[figures] 正文里引用了「${FIG_WORD} ${n}」，但这篇只有 ${total} 张带图注的图。` +
              `（图号只给写了图注的图，见 utils/rehype/figures.ts）`
          );
        }
      }
    }
    for (const child of node.children ?? []) walk(child);
  };
  walk(tree);
}

export function rehypeFigures() {
  return (tree: Node, file: FileWithFrontmatter) => {
    /* ⚠️ 计数器建在这里，不是外层 —— 外层的话第二篇会接着上一篇的号数。
       理由写在文件顶部「三、图号」那段。 */
    const figures: FigureEntry[] = [];

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
            const n = figures.length + 1;
            const id = `fig-${n}`;
            const label = `${FIG_WORD} ${n}`;
            figure.properties!.id = id;
            figures.push({ id, label, caption });

            figure.children!.push({
              type: "element",
              tagName: "figcaption",
              properties: {},
              children: [
                /*
                  编号是图注里的一个真元素，不是 ::before。样式（间距、字重）
                  在 typography.css 的 .fig-label 上 —— 和原来那条 ::before
                  一模一样，换的只是它从哪儿来。
                */
                {
                  type: "element",
                  tagName: "span",
                  properties: { className: ["fig-label"] },
                  children: [{ type: "text", value: label }],
                },
                { type: "text", value: caption },
              ],
            });
          }

          kids[i] = figure;
          continue;
        }

        walk(child);
      }
    };
    walk(tree);

    checkFigureRefs(tree, figures.length);

    /* 少于两张就不往下传：侧栏的图表目录和文章目录用同一条规则
       （见 components/TableOfContents.astro 里那段）—— 只有一条的清单
       不告诉读者任何事。判断留在页面那边做，这里只负责如实交出来。 */
    const frontmatter = file.data?.astro?.frontmatter;
    if (frontmatter) frontmatter.figures = figures;
  };
}
