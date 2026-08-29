/*
  自定义块：在**纯 .md 里**写出 markdown 本身没有的结构。

  ── 为什么走这条路，而不是 .mdx ──

  常规做法是把文章改成 .mdx，然后直接写 Astro 组件。这个站不能那么干：
  public/admin/config.yml 里文章集合写死了 `extension: md`，改成 .mdx
  那些文章就从后台消失了 —— 而「后台改 → 提交 main → Cloudflare 构建」
  是发文的主路径（见 .github/workflows/ci.yml 开头）。为了排版糖切断主路径
  不划算，这个判断在 utils/rehype/figures.ts 顶部已经下过一次。

  remark-directive 给的是第三条路：它把一套 CommonMark 社区约定的语法
  （:::name / ::name / :name）解析成节点，文件扩展名还是 .md，后台照常认。

  ── 怎么把节点变成 HTML ──

  不需要 rehype-components 之类的额外依赖。remark-directive 的官方用法是
  往节点上挂 data.hName / data.hProperties，mdast-util-to-hast 转 hast 时
  会认这两个字段 —— 也就是「这个节点最后请渲染成这个标签、带这些属性」。
  下面每种块就是几行这样的赋值。

  ── 加一种新块要改什么 ──

    1. 在 HANDLERS 里加一条 `名字: (node) => { ... }`
    2. 要样式的话去 styles/typography.css 加选择器

  没登记的指令**原样留在树里**，由 mdast-util-to-hast 的默认处理兜底
  （容器型会退化成一个 <div>，内容不会丢）。故意不报错：文章是后台在编辑的，
  写错一个指令名就让整站构建失败，代价比显示成一个普通 div 大得多。
*/

/*
  和 readingTime.ts / mathFlag.ts 一样，只声明用得到的字段，不引 @types/mdast。
  directive 相关的三个 type 来自 mdast-util-directive。
*/
type Node = {
  type: string;
  name?: string;
  value?: string;
  /* link 节点用；下面 :::source 的来源名可以是个链接 */
  url?: string;
  attributes?: Record<string, string | null | undefined> | null;
  data?: {
    hName?: string;
    hProperties?: Record<string, unknown>;
    /* mdast-util-directive 声明的就是 boolean | null | undefined。
       少写一个 null，这个类型就和 unified 的 Transformer<Root, Root> 对不上，
       astro check 会报 ts(2322) —— 报错链一路指到 ParagraphData 才看得出原因。 */
    directiveLabel?: boolean | null;
  };
  children?: Node[];
};

export type DirectiveOptions = {
  /*
    剧透块没写标题时用的那行字。

    没走 i18n 是因为 remark 插件跑在构建管道里，拿不到 Astro 的 locale
    上下文（那是渲染期的东西）。站现在只有 zh 一个 locale
    （astro.config.ts 的 i18n.locales），所以这里传一个常量就够；
    真加了第二种语言，得把这个值改成按文章语言取。
  */
  spoilerLabel?: string;
};

const CONTAINER = "containerDirective";

/*
  取出块的标题，并把它从正文里摘掉。

  两种写法都支持：

      :::spoiler[第三章的结局]      ← 方括号，remark-directive 会把它解析成
                                       第一个子节点并打上 directiveLabel
      :::spoiler{title="第三章的结局"} ← 属性写法

  方括号那种优先。它已经是一棵 mdast 子树（可以带 **加粗**、`代码`），
  所以直接把它改造成 <summary> 就行，不用把它拍平成字符串。
*/
function takeLabel(node: Node, fallback: string): Node {
  const first = node.children?.[0];

  if (first?.data?.directiveLabel) {
    first.data.hName = "summary";
    return first;
  }

  const title = node.attributes?.title;
  const text = typeof title === "string" && title.trim() ? title : fallback;

  /*
    造一个新节点插到最前面。type 写 paragraph 是因为它得是个合法的 mdast
    节点才能被继续处理，真正决定标签的是 data.hName。
  */
  const summary: Node = {
    type: "paragraph",
    data: { hName: "summary" },
    children: [{ type: "text", value: text }],
  };
  node.children = [summary, ...(node.children ?? [])];
  return summary;
}

type Handler = (node: Node, options: Required<DirectiveOptions>) => void;

const HANDLERS: Record<string, Handler> = {
  /*
    剧透。渲染成原生 <details> —— 展开/收起、键盘操作、读屏播报全都是
    浏览器自带的，一行 JS 都不用写，也不会在翻页后失效。

        :::spoiler[第三章的结局]
        主角其实早就死了。
        :::
  */
  spoiler(node, options) {
    if (node.type !== CONTAINER) return;
    takeLabel(node, options.spoilerLabel);
    node.data ??= {};
    node.data.hName = "details";
    node.data.hProperties = { class: "spoiler" };
  },

  /*
    引文框：一整段外来引文，**带名带署名**地框起来。

        :::source[Atomic Rockets · Basic Design]{href="https://…" by="Winchell Chung"}
        这些方法「horribly simplistic」，但「far better than just making up your figures」。
        :::

    来源名也可以写成属性：`:::source{from="…"}`。方括号那种优先，
    因为它是一棵 mdast 子树，可以带 **加粗**、`代码`、行内链接。
    三样都是可选的：只写正文也能用，退化成一个纯规则线的框。

    ── 为什么值得单开一种块 ──

    这站干的事就是译介，引文不是修辞而是主体内容。普通的 > 引用只说
    「这段是引来的」，说不出**从哪引的**、**谁写的** —— 而这两件事恰恰是
    读者判断可信度的全部依据。Atomic Rockets 那套 figure.textbox 就是这个
    思路（顶栏写来源、底栏写署名），只是他家用深蓝色块，这里用规则线：
    上下两条粗线、头栏下一条发丝线，和三线表是同一族（见 typography.css）。

    ── 输出结构 ──

        <figure class="quote-frame">
          <div class="quote-frame-head">来源名</div>   ← 可选
          <blockquote>…正文…</blockquote>
          <figcaption class="quote-frame-foot">署名</figcaption>  ← 可选
        </figure>

    正文包一层 <blockquote> 是语义要求：这确实是引用，读屏和「引文」类
    工具认的是这个标签，不是那个 class。
  */
  source(node) {
    if (node.type !== CONTAINER) return;

    const attrs = node.attributes ?? {};
    const attr = (key: string): string => {
      const value = attrs[key];
      return typeof value === "string" ? value.trim() : "";
    };
    const href = attr("href");
    const by = attr("by");

    /*
      头栏取值：方括号标签优先，其次 {from="…"}。两个都没有就不画头栏
      —— 不造一句「来源」之类的占位，那种默认文案只会骗读者。
    */
    let head: Node | undefined;
    const first = node.children?.[0];
    if (first?.data?.directiveLabel) {
      head = first;
      node.children = node.children?.slice(1) ?? [];
    } else if (attr("from")) {
      head = {
        type: "paragraph",
        children: [{ type: "text", value: attr("from") }],
      };
    }

    const children: Node[] = [];

    if (head) {
      /*
        给了 href 就把整个来源名包成链接。包在**外面**而不是自己造一个
        <a> 塞文本进去：方括号标签里可能已经有加粗、行内代码，
        整棵子树平移过去就行。
      */
      if (href) {
        head.children = [
          { type: "link", url: href, children: head.children ?? [] },
        ];
      }
      head.data = {
        ...head.data,
        hName: "div",
        hProperties: { class: "quote-frame-head" },
      };
      children.push(head);
    }

    children.push({ type: "blockquote", children: node.children ?? [] });

    if (by) {
      children.push({
        type: "paragraph",
        data: {
          hName: "figcaption",
          hProperties: { class: "quote-frame-foot" },
        },
        children: [{ type: "text", value: by }],
      });
    }

    node.children = children;
    node.data ??= {};
    node.data.hName = "figure";
    node.data.hProperties = { class: "quote-frame" };
  },
};

function walk(node: Node, options: Required<DirectiveOptions>): void {
  const handler = node.name ? HANDLERS[node.name] : undefined;
  if (handler) {
    handler(node, options);
    /*
      handler 只认容器型（:::）。写成行内（:spoiler[...]）或叶子型
      （::spoiler）时它什么都不做，节点就会落到 mdast-util-to-hast 的默认
      处理上 —— 那个默认是 <div>，而行内位置上的 <div> 会被浏览器从 <p> 里
      甩出去，段落当场断成三截。

      所以这里兜一道：登记过的名字用错了位置，退化成 <span>。
      语义没了，但至少是合法 HTML，句子还是一句。
    */
    if (node.type !== CONTAINER && !node.data?.hName) {
      node.data ??= {};
      node.data.hName = "span";
    }
  }
  for (const child of node.children ?? []) walk(child, options);
}

export function remarkDirectives(options: DirectiveOptions = {}) {
  const resolved: Required<DirectiveOptions> = {
    spoilerLabel: options.spoilerLabel ?? "剧透",
  };
  return (tree: Node) => walk(tree, resolved);
}
