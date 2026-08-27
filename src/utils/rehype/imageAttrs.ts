/*
  给**远程**正文图补上尺寸和懒加载。

  2026-08-26 之前这个插件管所有正文图：那时候图片在 R2 上，对 Astro 来说
  全是远程地址，构建时既不下载也不知道多大，markdown 的 `![](...)` 出来
  就是一个裸 <img>，图一到下面的正文就往下跳一次（CLS）。

  图片搬进 src/content/posts/img/ 之后，本地图这一整套 Astro 自己做了 ——
  实测把这个插件从管道里摘掉，本地图的 loading / decoding / width / height
  一个字节都不变。所以它现在**只对远程图有意义**，而远程图已经没有了
  （check:posts 会提醒你把它们搬进来）。

  那为什么还留着：万一哪天正文里真出现一张外站的图，没有它就连
  loading="lazy" 都没有。40 行、零依赖、对本地图完全是空转 ——
  留着比删掉划算。

  尺寸仍然从**文件名**来，因为远程图没有别的来源：

      https://example.org/dyson-sphere-1600x900.webp
                                       ↑ 宽 x 高

  没带尺寸的**不报错**，只是拿不到 width/height（懒加载照加）。

  **只管 markdown 的 `![](...)` 写法**（实测过）。手写的 <img> 这里看不到：
  .md 里的原始 HTML 不会被解析成 hast 元素（管道里没有 rehype-raw，
  它作为整块 raw 文本原样输出），.mdx 里的 <img> 则是 mdxJsxFlowElement，
  不是 element。两种都不会走到下面的 walk。
  所以手写 <img> 的尺寸和 loading 得自己写全 —— check-posts 会提醒。
*/

import { IMG_SIZE_IN_NAME } from "../../../scripts/post-rules.mjs";

/*
  hast 节点里我们真正用到的那一小块形状。

  故意不装 @types/hast：整个插件只碰 type / tagName / properties / children
  四个字段，为它们引一个类型包不值得。代价是下面这个类型比真实的 hast 宽松，
  改动这个文件时自己留神。
*/
type Node = {
  type: string;
  tagName?: string;
  properties?: Record<string, unknown>;
  children?: Node[];
};

function decorate(node: Node) {
  const props = (node.properties ??= {});

  /*
    懒加载和异步解码对任何一张正文图都成立，不依赖文件名。

    全都设成 lazy，包括第一张 —— 文章页在图之前还有面包屑、标题、日期和
    摘要，正文里的第一张图基本不会落在首屏。真遇到要抢首屏的图，
    把那一张用 .mdx 手写成 <img loading="eager">，下面这行不会覆盖它。
  */
  props.loading ??= "lazy";
  props.decoding ??= "async";

  // 手写过任意一边，就当作作者已经想清楚了，整个尺寸这块都不碰
  if (props.width !== undefined || props.height !== undefined) return;

  // 查询串和锚点先切掉：foo-800x600.webp?v=2 也该认得出来
  const src = typeof props.src === "string" ? props.src : "";
  const match = IMG_SIZE_IN_NAME.exec(src.split(/[?#]/)[0] ?? "");
  if (!match) return;

  props.width = Number(match[1]);
  props.height = Number(match[2]);
}

function walk(node: Node) {
  if (node.type === "element" && node.tagName === "img") decorate(node);
  for (const child of node.children ?? []) walk(child);
}

export function rehypeImageAttrs() {
  return (tree: Node) => walk(tree);
}
