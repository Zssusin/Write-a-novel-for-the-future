import type { CollectionEntry } from "astro:content";

/*
  文章的篇幅：字数和估算分钟数。

  这两个数不是这里算的 —— utils/remark/readingTime.ts 在 remark 阶段数完，
  塞进 frontmatter。这个文件只负责**从列表页够得着的地方**把它们取出来。

  为什么需要这一层：文章页是 `const { remarkPluginFrontmatter } = await render(post)`，
  顺手就拿到了 —— 它本来就要 render 一次取 Content 和 headings。列表页不一样，
  一页十几张卡片，为了两个数字挨个 render 太贵。

  好在内容层（Content Layer）在**加载集合的时候**就把渲染结果连同 remark 写进的
  frontmatter 一起存进了数据仓，getCollection 拿到的条目上直接挂着：

      post.rendered.metadata.frontmatter.wordCount

  实测三篇文章都在，值和文章页铭牌上那一格一模一样 —— 是同一份数据被读了两次，
  不是各算一遍。所以列表加字数是**零构建开销**，不用担心页数多了变慢。

  ⚠️ 取不到就返回 undefined，别兜底成 0：「0 字」是错的信息，不显示只是少一条信息。
  真取不到只有两种情况 —— readingTime 插件被从 astro.config.ts 摘了，
  或者条目根本没渲染过（非 markdown 的 loader）。两种都不该靠假数据糊过去。
*/

export type PostExtent = {
  words?: number;
  minutes?: number;
};

/*
  frontmatter 在生成的类型里落在 RenderedContent.metadata 的索引签名上，
  所以是 unknown，得自己收窄。这不是偷懒 —— 那份类型是 Astro 生成的，
  改不动，而且 remark 插件往里写什么本来就只有我们自己知道。
*/
function readNumber(source: unknown, key: string): number | undefined {
  if (typeof source !== "object" || source === null) return undefined;
  const value = (source as Record<string, unknown>)[key];
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? value
    : undefined;
}

export function getPostExtent(post: CollectionEntry<"posts">): PostExtent {
  const frontmatter = post.rendered?.metadata?.frontmatter;

  return {
    words: readNumber(frontmatter, "wordCount"),
    minutes: readNumber(frontmatter, "readingTime"),
  };
}
