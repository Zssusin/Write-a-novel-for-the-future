/*
  给正文里的图片补上尺寸和懒加载。

  为什么需要：正文图走的是 /img/ 那条 R2 路由（见 docs/图片工作流.md），
  对 Astro 来说是**远程地址** —— 构建时既不下载也不知道它多大，所以
  markdown 的 `![](...)` 出来就是一个裸 <img>，没有 width/height。浏览器在图
  下载完之前不知道该给它留多少位置，图一到，下面的正文就往下跳一次（CLS）。
  一篇文章几张图，就跳几次。

  为什么不交给 Astro 处理远程图：docs/图片工作流.md 第 6 节已经论证过 ——
  配 `image.domains` 会让构建期去下载每一张图再处理，又慢又吃内存，
  等于把 R2 的好处抵消掉。那个决定这里不推翻。

  所以尺寸从**文件名**来：

      /img/2026/dyson-sphere-1600x900.webp
                             ↑ 宽 x 高

  这和既有的「换内容就换文件名」是同一套办法 —— 文件名本来就是这个体系里的
  真相来源，顺手让它多带一个事实而已。零构建期网络、零运行时开销、
  也不需要任何外部依赖。

  没带尺寸的图**不报错**，只是拿不到 width/height（懒加载照加）。
  scripts/check-posts.mjs 会在 npm run check:posts 时把它们列出来。

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
