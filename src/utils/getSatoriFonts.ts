import type { SatoriOptions } from "satori";
import { fontData, experimental_getFontFileURL } from "astro:assets";
import { getFontPathByWeight } from "./getFontPathByWeight";

/*
  给 satori 准备字体。两个 OG 图生成器（src/pages/og.png.ts 和
  src/pages/posts/[...slug]/index.png.ts）都从这里拿。

  ===== 为什么需要这个文件 =====

  satori 只会用你显式传给它的字体，没有系统字体可回落。而 Google Sans Code
  一个汉字都没有 —— 所以在加这段之前，OG 图上的中文全是豆腐块（□□□□□）。
  这个 bug 会安静地活很久：构建不报错，Astro 也不警告，只有真的把
  dist/og.png 打开、或者把链接分享出去，才看得出来。

  ===== 为什么是「按需子集」而不是塞一份字体进仓库 =====

  全量 Noto Sans SC 大约 10 MB。这个站的整套设计（图片走 R2、构建产物不进
  仓库）就是为了让仓库保持小，塞一份 10 MB 的字体进去是反着来的。

  所以这里改成向 Google Fonts 要一份**刚好够这张图用**的子集：
  用 css2 接口的 text= 参数，把这张图上出现过的汉字报上去。
  实测一个 13 字的标题约 5 KB，一段 30 字的描述约 9 KB。

  顺带说明为什么不能「下载整个字体再交给 satori」：Google 那边的
  Noto Sans SC 是切成 101 个 unicode-range 分片发的，拼不回一个文件。
  text= 是唯一能一次拿到「一个文件、含指定字」的办法。
*/

/*
  Google Fonts 会按 User-Agent 决定发什么格式：现代浏览器拿 woff2，
  而 **satori 只认 ttf / otf / woff，不认 woff2**。报一个老 UA 就退回 truetype。
  这是这段代码里最容易被「顺手清理掉」的一行，别删。
*/
const LEGACY_UA = "Mozilla/5.0 (Windows NT 6.1; WOW64)";

/*
  U+2E7F 往后是 CJK 部件、汉字、CJK 标点（、。）和全角形式（：）。
  拉丁字母、数字、以及 Google Sans Code 本来就画得出的西文标点都在这之前，
  不必向 Noto 要 —— 少要一个字就少几百字节。
*/
const isCJK = (char: string) => char.codePointAt(0)! > 0x2e7f;

/*
  同一次构建里，站名和站点描述会在每张图上重复出现。缓存按
  「字重 + 排序去重后的字符集」做键，命中就不再走网络。
*/
const subsetCache = new Map<string, ArrayBuffer | null>();

async function loadCJKSubset(
  text: string,
  weight: 400 | 700
): Promise<ArrayBuffer | null> {
  const chars = [...new Set([...text])].filter(isCJK).sort().join("");

  if (!chars) return null;

  const cacheKey = `${weight}:${chars}`;
  const cached = subsetCache.get(cacheKey);
  if (cached !== undefined) return cached;

  /*
    整段包在 try 里，失败就返回 null。

    这是有意的取舍：这里多了一个**构建时的外部网络依赖**，而 Cloudflare
    的构建机上 fonts.googleapis.com 偶尔抽风是完全可能的。那种时候，
    「OG 图上的中文缺字」远好过「整站发布失败」—— 前者只影响分享卡片的观感，
    后者是文章根本上不去。
  */
  try {
    const css = await fetch(
      `https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@${weight}` +
        `&text=${encodeURIComponent(chars)}`,
      { headers: { "User-Agent": LEGACY_UA } }
    ).then(res => res.text());

    const url = css.match(/src:\s*url\(([^)]+)\)/)?.[1];
    if (!url) throw new Error("Google Fonts 的响应里没有字体地址");

    const data = await fetch(url).then(res => res.arrayBuffer());
    subsetCache.set(cacheKey, data);
    return data;
  } catch (error) {
    console.warn(
      `[og] 取 Noto Sans SC 子集失败，这张图上的中文会缺字：${String(error)}`
    );
    subsetCache.set(cacheKey, null);
    return null;
  }
}

/**
 * 组装 satori 的 fonts 数组。
 *
 * @param texts 这张图上会出现的所有文字。用来算需要哪些汉字 ——
 *   漏传一段，那段的中文就是豆腐块，所以新增文字节点时记得一起传进来。
 * @param requestUrl 当前请求的 URL，`experimental_getFontFileURL` 要用它
 *   拼出构建期能取到本地字体文件的地址。
 */
export async function getSatoriFonts(
  texts: string[],
  requestUrl: URL
): Promise<SatoriOptions["fonts"]> {
  const fonts = fontData["--font-google-sans-code"];

  /*
    **必须显式要 woff。** astro.config.ts 里那套字体生成两种格式：
    woff2 给浏览器（是可变字体，两个文件覆盖全部字重），woff 给这里 ——
    satori 只认 ttf / otf / woff，不认 woff2。

    不传这个参数的话默认找 "truetype"，现在没有 ttf 了，于是
    getFontPathByWeight 会退到该字重的第一个文件，构建挂在
    `Error: Unsupported OpenType signature wOF2`。踩过一次。
  */
  const regularFontPath = getFontPathByWeight(fonts, 400, { format: "woff" });
  const boldFontPath = getFontPathByWeight(fonts, 700, { format: "woff" });

  if (regularFontPath === undefined || boldFontPath === undefined) {
    throw new Error(
      "找不到 OG 图要用的字体文件。检查 astro.config.ts 的 fonts.formats " +
        '里还有没有 "woff" —— satori 不认 woff2。'
    );
  }

  const allText = texts.join("");

  const [regularData, boldData, cjkRegular, cjkBold] = await Promise.all([
    fetch(experimental_getFontFileURL(regularFontPath, requestUrl)).then(res =>
      res.arrayBuffer()
    ),
    fetch(experimental_getFontFileURL(boldFontPath, requestUrl)).then(res =>
      res.arrayBuffer()
    ),
    loadCJKSubset(allText, 400),
    loadCJKSubset(allText, 700),
  ]);

  return [
    {
      name: "Google Sans Code",
      data: regularData,
      weight: 400,
      style: "normal",
    },
    { name: "Google Sans Code", data: boldData, weight: 700, style: "normal" },
    /*
      satori 是**逐字**在这个数组里找能画的字体的，所以顺序就是优先级：
      拉丁字母命中前两项，汉字落到下面这两项。
    */
    ...(cjkRegular
      ? ([
          {
            name: "Noto Sans SC",
            data: cjkRegular,
            weight: 400,
            style: "normal",
          },
        ] as const)
      : []),
    ...(cjkBold
      ? ([
          { name: "Noto Sans SC", data: cjkBold, weight: 700, style: "normal" },
        ] as const)
      : []),
  ];
}

/** 两个生成器的根节点共用的字体栈。汉字靠 satori 的逐字回退落到 Noto。 */
export const OG_FONT_FAMILY = "Google Sans Code, Noto Sans SC";
