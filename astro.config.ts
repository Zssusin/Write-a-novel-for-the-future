import {
  defineConfig,
  envField,
  fontProviders,
  svgoOptimizer,
} from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import { unified } from "@astrojs/markdown-remark";
import remarkToc from "remark-toc";
import remarkCollapse from "remark-collapse";
import remarkMath from "remark-math";
import remarkDirective from "remark-directive";
import remarkCjkFriendly from "remark-cjk-friendly";
import rehypeKatex from "rehype-katex";
import rehypeCallouts from "rehype-callouts";
import {
  transformerNotationDiff,
  transformerNotationHighlight,
  transformerNotationWordHighlight,
} from "@shikijs/transformers";
import { transformerFileName } from "./src/utils/transformers/fileName";
import { rehypeImageAttrs } from "./src/utils/rehype/imageAttrs";
import { rehypeFigures } from "./src/utils/rehype/figures";
import { remarkReadingTime } from "./src/utils/remark/readingTime";
import { remarkMathFlag } from "./src/utils/remark/mathFlag";
import { remarkDirectives } from "./src/utils/remark/directives";
import { cacheHeaders } from "./src/integrations/cacheHeaders";
import config from "./astro-paper.config";

export default defineConfig({
  site: config.site.url,
  integrations: [
    mdx(),
    sitemap({
      filter: page =>
        config.features?.showArchives !== false || !page.endsWith("/archives/"),
    }),
    // 把根目录的 _headers 复制进 dist/。为什么不能直接放 public/，见那个文件顶部
    cacheHeaders(),
  ],
  i18n: {
    // Keep in sync with `site.lang` in astro-paper.config.ts.
    locales: ["zh"],
    defaultLocale: "zh",
    routing: {
      prefixDefaultLocale: false,
    },
  },
  image: {
    // 试验：让正文图自带 srcset。手机上一张 1280 宽的图现在是原样发的。
    layout: "constrained",
  },
  markdown: {
    processor: unified({
      remarkPlugins: [
        /*
          中文里的加粗。CommonMark 判断一对 ** 能不能成对，看的是紧挨着它的
          那个字是不是标点 —— 而中文的《》（）“” 全是标点，于是这种再正常
          不过的写法两头都判不成立，整段加粗**静默失效**，星号原样打在页面上：

            有一部名为**《飞向星空》（To the Stars）**的宏大史诗
                      ↑ 后面是《，开不了            ↑ 前面是），收不了

          它不报错、构建不失败，只有看渲染结果才发现。project-to-the-stars
          一篇里就中了三处（2026-08-26）。

          这个插件实装的是 CommonMark 那份 CJK 友好提案：汉字和标点相邻时
          按中日韩的规矩判断，上面那行就正常加粗了。装它而不是在正文里
          手动补空格 —— 补空格等于让每个作者都记住这条规则，而且中文里
          会多出可见的空格。

          只放宽、不收紧：原来能加粗的写法一个都不会变（升级前后 diff 过
          全部三篇文章的 HTML，只有上面那三处从星号变成了 <strong>）。
        */
        remarkCjkFriendly,
        remarkToc,
        [remarkCollapse, { test: "Table of contents" }],
        /*
          remarkMath 把 $...$ / $$...$$ 解析成 inlineMath / math 节点，
          真正渲染成 HTML 的是下面 rehype 那行的 rehypeKatex。

          remarkMathFlag 必须**紧跟在 remarkMath 后面** —— 它数的就是上面
          那两种节点，排到前面去会永远数到 0，而且不报错，只是全站公式
          悄悄丢掉样式表。理由详见那个文件顶部。
        */
        remarkMath,
        remarkMathFlag,
        /*
          自定义块（:::spoiler 之类）。同样是两步：remarkDirective 只负责
          **解析出**指令节点，remarkDirectives（复数，我们自己写的那个）
          才把节点变成具体的标签，所以顺序不能反。
          加新块改的是 utils/remark/directives.ts 里的 HANDLERS。
        */
        remarkDirective,
        remarkDirectives,
        /*
          只读树、不改树，所以位置无所谓；放最后是为了和下面 rehype 那行
          「加工的放前面、统计的放后面」保持同一个读法。

          顺带：它只收 text / inlineCode 节点，math 那两种不在名单里，
          所以公式里的符号不会被算进中文字数 —— 这是想要的。
        */
        remarkReadingTime,
      ],
      // imageAttrs 放最后：让它看得到前面插件生成出来的 <img>
      rehypePlugins: [
        rehypeCallouts,
        rehypeFigures,
        rehypeKatex,
        rehypeImageAttrs,
      ],
    }),
    shikiConfig: {
      themes: { light: "min-light", dark: "night-owl" },
      defaultColor: false,
      wrap: false,
      transformers: [
        transformerFileName({ style: "v2", hideDot: false }),
        transformerNotationHighlight(),
        transformerNotationWordHighlight(),
        transformerNotationDiff({ matchAlgorithm: "v3" }),
      ],
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
  /*
    这套字体**只渲染拉丁字符** —— Google Sans Code 没有汉字，中文一律落到
    src/styles/theme.css 里那条 --font-stack-app 后面的系统字体。所以这里每多
    一个变体，就是给「正文里那些英文术语和数字」多下载一整套字面。

    每个字段都是有意写的，别随手加回去：

    weights —— 故意没有 300。全站唯一用 font-light 的地方是面包屑
      （Breadcrumb.astro），而那里的拉丁字符只有页码数字和 »。没有 300 这个
      字面时，浏览器给拉丁部分退到最近的 400，中文那半仍然由系统字体按 300 渲染
      （系统有 Light 字面就用，没有就自己合成）—— 视觉上几乎看不出来，
      但省掉两个变体（300 正体 + 300 斜体）。
      500 / 600 / 700 和斜体都留着：卡片标题里的 "Atomic Rockets"、正文英文术语、
      markdown 的 <em> 都是真会出现的拉丁文字，缺了字面会让它和旁边的中文字重对不上。

    formats —— **两个都需要，而且 woff2 必须排在后面**，这两点都是踩出来的：

      · woff2 是给浏览器的。Google Sans Code 的 woff2 是**可变字体**，两个文件
        （正体 + 斜体，共 76 KB）就覆盖了全部四个字重；老格式则是逐字重的静态
        实例，四个字重两种字形 = 8 个文件。这个主题原本写的是 ["woff", "ttf"]，
        **根本没有 woff2** —— 于是构建产物里躺着 932 KB、20 个字体文件。

      · woff 是给 OG 图生成器的。satori 只认 ttf / otf / woff，**不认 woff2**，
        只留 woff2 的话构建直接挂在
        `Error: Unsupported OpenType signature wOF2`。
        src/utils/getSatoriFonts.ts 显式要 format: "woff" 取的就是这一份。

      · 顺序为什么反着写：Astro **不是**把两种格式合进同一条 src，而是给每种
        格式生成独立的 @font-face。同名同字重同字形的规则里，**后声明的赢**，
        所以 woff2 写在后面浏览器才会去下它 —— 写成 ["woff2", "woff"] 的话
        读者下到的是 woff，那 76 KB 的可变字体白生成。

      所以别把 woff 删掉，也别把顺序调「顺」：它不占读者带宽，只占部署体积。

    subsets —— 不要写。默认 ["latin"] 正好够：中文走系统字体，
      Δv 里那个希腊字母 Δ 本来就不在 latin 子集里，一直是靠系统字体兜的。
  */
  fonts: [
    {
      name: "Google Sans Code",
      cssVariable: "--font-google-sans-code",
      provider: fontProviders.google(),
      fallbacks: ["monospace"],
      weights: [400, 500, 600, 700],
      styles: ["normal", "italic"],
      formats: ["woff", "woff2"],
      /*
        这一段是**省流量的关键**，不是可选装饰。

        Astro 给老格式（woff）生成的 @font-face 默认**不带 unicode-range**，
        等于宣称「所有码位我都能画」。而本站正文以中文为主 —— 于是浏览器为了
        每个汉字都去下载那 8 个 woff 静态字面，翻遍没有汉字，再回落到系统字体。
        实测一篇文章页因此下了 7 个文件、211 KB，全是白下的。

        显式写出真实覆盖范围之后：范围内的字符由 woff2 那条规则接走
        （同名同字重，后声明的赢），范围外的汉字**两条都不匹配**，
        浏览器直接用系统字体，不发任何请求。

        这串范围抄的是 Google 自己给 latin 子集声明的那一串，改 subsets 时要跟着改。
      */
      unicodeRange: [
        "U+0000-00FF",
        "U+0131",
        "U+0152-0153",
        "U+02BB-02BC",
        "U+02C6",
        "U+02DA",
        "U+02DC",
        "U+0304",
        "U+0308",
        "U+0329",
        "U+2000-206F",
        "U+20AC",
        "U+2122",
        "U+2191",
        "U+2193",
        "U+2212",
        "U+2215",
        "U+FEFF",
        "U+FFFD",
      ],
    },
  ],
  env: {
    schema: {
      PUBLIC_GOOGLE_SITE_VERIFICATION: envField.string({
        access: "public",
        context: "client",
        optional: true,
      }),
    },
  },
  experimental: {
    svgOptimizer: svgoOptimizer(),
  },
});
