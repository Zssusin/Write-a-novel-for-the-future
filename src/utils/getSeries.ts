import type { CollectionEntry } from "astro:content";
import { postFilter } from "./postFilter";
import { getPostExtent } from "./getPostExtent";

export type SeriesPart = {
  part: number;
  title: string;
  id: string;
  filePath: string | undefined;
  /*
    这一部分有多长。目录里摆出来，读者才判断得了「还剩四部分」是剩两千字
    还是剩两万字 —— 这是决定要不要现在开始读的主要依据。

    可选：readingTime 插件没跑或条目没渲染过时取不到，那就不显示，
    不要拿 0 顶上（见 getPostExtent.ts 末尾）。
  */
  words?: number;
};

/**
 * 按系列名把文章归堆，每堆内部按 `part` 升序。
 *
 * 按 part 排而不按时间排：回填旧部分、改发布时间、补一篇插在中间，
 * 都不应该改变阅读顺序 —— 顺序是作者定的，不是时间戳定的。
 *
 * 走 `postFilter`，所以草稿和还没到点的定时文章不会从目录里泄漏出去。
 */
export function getSeriesIndex(
  posts: CollectionEntry<"posts">[]
): Map<string, SeriesPart[]> {
  const index = new Map<string, SeriesPart[]>();

  for (const post of posts.filter(postFilter)) {
    const series = post.data.series;
    if (!series) continue;

    const parts = index.get(series.name) ?? [];
    parts.push({
      part: series.part,
      title: post.data.title,
      id: post.id,
      filePath: post.filePath,
      words: getPostExtent(post).words,
    });
    index.set(series.name, parts);
  }

  for (const parts of index.values()) {
    parts.sort((a, b) => a.part - b.part);
  }

  return index;
}
