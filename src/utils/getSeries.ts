import type { CollectionEntry } from "astro:content";
import { postFilter } from "./postFilter";

export type SeriesPart = {
  part: number;
  title: string;
  id: string;
  filePath: string | undefined;
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
    });
    index.set(series.name, parts);
  }

  for (const parts of index.values()) {
    parts.sort((a, b) => a.part - b.part);
  }

  return index;
}
