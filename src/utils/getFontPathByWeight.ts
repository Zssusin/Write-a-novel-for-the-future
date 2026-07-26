import type { FontData } from "astro:assets";

export function getFontPathByWeight(
  fonts: FontData[],
  weight: number,
  options?: {
    style?: "normal" | "italic";
    format?: string;
  }
): string | undefined {
  const style = options?.style ?? "normal";
  const format = options?.format ?? "truetype";

  const matches = fonts.filter(
    font => font.weight === String(weight) && font.style === style
  );

  /*
    先在**所有**同字重同字形的条目里找指定格式，找不到才退回第一个。

    原来的写法是一进循环就在第一个匹配项里 find 格式、失败立刻退到
    src[0] 然后 return —— 于是「要 woff」在 formats: ["woff2", "woff"] 下
    会拿到 woff2，因为 Astro 给每种格式生成**独立的**条目，woff2 那条排在前面。
    结果是 satori 收到 woff2 直接挂：Unsupported OpenType signature wOF2。
    现在的写法和 formats 的顺序无关。
  */
  for (const font of matches) {
    const src = font.src.find(file => file.format === format);
    if (src) return src.url;
  }

  return matches[0]?.src[0]?.url;
}
