/*
  标记「这篇文章里有没有数学公式」，结果写进 frontmatter.hasMath。

  为什么需要这么一个标记：KaTeX 的样式表得单独 <link> 进来（理由写在
  scripts/sync-katex.mjs 顶部 —— 一句话是「Astro 按导入收集 CSS，不按渲染，
  而全站文章共用一个页面文件」）。既然要手动挂，就得知道该给哪些页面挂。

  **必须排在 remarkMath 后面**：math / inlineMath 这两种节点是 remarkMath
  解析 $...$ 和 $$...$$ 时造出来的，在它之前跑，树里一个都没有，
  这里就永远返回 false —— 而且不会报错，只是全站公式都变成没样式的裸文本。
  顺序写在 astro.config.ts 的 remarkPlugins 里，别调换。

  找到第一个就停：这里只回答「有没有」，不关心有几个。长文里第一个公式
  往往在前几段，扫全树纯属浪费。
*/

/*
  和 readingTime.ts / rehype 那两个插件一样，只声明用得到的字段，
  不引 @types/mdast。代价同样是类型比真实的 mdast 宽松。
*/
type Node = {
  type: string;
  children?: Node[];
};

type FileWithFrontmatter = {
  data?: {
    astro?: {
      frontmatter?: Record<string, unknown>;
    };
  };
};

/* remarkMath 产出的两种节点：$$...$$ 是 math，$...$ 是 inlineMath */
const MATH_NODES = new Set(["math", "inlineMath"]);

function hasMath(node: Node): boolean {
  if (MATH_NODES.has(node.type)) return true;
  for (const child of node.children ?? []) {
    if (hasMath(child)) return true;
  }
  return false;
}

export function remarkMathFlag() {
  return (tree: Node, file: FileWithFrontmatter) => {
    const frontmatter = file.data?.astro?.frontmatter;
    if (!frontmatter) return;
    frontmatter.hasMath = hasMath(tree);
  };
}
