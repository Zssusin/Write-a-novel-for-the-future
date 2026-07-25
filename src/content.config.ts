import { defineCollection } from "astro:content";
import { z } from "astro/zod";
import { glob } from "astro/loaders";
import config from "@/config";

export const BLOG_PATH = "src/content/posts";

const posts = defineCollection({
  loader: glob({ pattern: "**/[^_]*.{md,mdx}", base: `./${BLOG_PATH}` }),
  schema: ({ image }) =>
    z.object({
      /*
        永久标识。**写下之后永不修改。**

        文章的 URL 是从文件路径推导的（见 utils/getPostPaths.ts），
        所以改个文件名、挪个目录，URL 就变了。以后要接评论、浏览量、
        wiki 反向链接，这些数据必须挂在一个不会变的键上 —— 就是 uid。
        拿 URL 或文件名当键，重命名一次就把旧数据变成孤儿。

        故意设成必填、不给默认值：漏写就让构建失败。
        事后补一个键，比事后迁移一堆已经写歪的数据便宜得多。

        首位限定小写字母：纯数字的 uid 会被 YAML 读成数字而不是字符串。
        「不重复」是跨文件的约束，zod 管不到，由 scripts/check-posts.mjs 校验。

        长度放到 8–40 位，是为了同时容纳两种来源，两种都只生成一次、之后不变：

          npm run uid   → 8 位，手写文章用，短、好认
          后台（Sveltia CMS 的 uuid 组件）→ 27 位，形如 uC5T6KX3M6N7G4Y2Z1A0B9C8D7E
                          浏览器里跑不了 npm，只能让它自己生成。
                          它的 prefix 配成 "u"，首位是字母这条就还成立。
      */
      uid: z
        .string()
        .regex(
          /^[a-z][0-9a-zA-Z-]{7,39}$/,
          "uid 要 8–40 位：首位小写字母，其余字母、数字或连字符。用 `npm run uid` 生成，或由后台自动生成"
        ),
      /*
        连载系列。一个主题拆成多部分陆续发出时填这里：

          series:
            name: 戴森球的工程学
            part: 2

        故意用嵌套对象，而不是 seriesName + seriesPart 两个平铺字段 ——
        「要么都填、要么都不填」这条约束就成了结构本身，不需要额外校验。

        总篇数**不写在这里**：那是数文件数得出来的，写死一定会和现实脱节。
        「同一系列里 part 不重复」是跨文件约束，zod 管不到，
        由 scripts/check-posts.mjs 校验。

        nullable 是为后台留的：Sveltia CMS 的 object 组件在「没填」时
        可能写出 `series: null` 而不是干脆省掉这个键。光有 optional 会报
        「Expected object, received null」—— 每一篇不带系列的后台文章都会挂。
        （modDatetime 上面本来就是这个写法，同一个原因。）
      */
      series: z
        .object({
          name: z.string(),
          part: z.number().int().positive(),
        })
        .optional()
        .nullable(),
      /*
        原文出处。schema 里是 optional —— 因为原创文章没有出处；
        但**译文必须填**。schema 判断不了「这篇是不是译文」，所以靠约定。

        note 是留白：授权情况写什么由你决定（「已获作者邮件授权」、
        「依据 CC BY-SA 4.0 转译」……）。这里不预设，也不代你声明。
      */
      source: z
        .object({
          title: z.string(),
          author: z.string().optional(),
          url: z.url({
            protocol: /^https?$/,
            message: "原文链接要是完整的 http(s) 地址",
          }),
          note: z.string().optional(),
        })
        .optional()
        .nullable(),
      author: z.string().default(config.site.author),
      /*
        coerce 而不是 z.date()：YAML 只有在值**没加引号**时才把它读成日期。
        后台写出来的是不是带引号，取决于它内部的 YAML 序列化器，我们管不着 ——
        `z.date()` 遇到带引号的版本会报「Expected date, received string」。
        coerce 两种都吃，等于把这一整类失败去掉。
      */
      pubDatetime: z.coerce.date(),
      modDatetime: z.coerce.date().optional().nullable(),
      title: z.string(),
      featured: z.boolean().optional(),
      draft: z.boolean().optional(),
      tags: z.array(z.string()).default(["others"]),
      ogImage: image().or(z.string()).optional(),
      description: z.string(),
      canonicalURL: z.string().optional(),
      hideEditPost: z.boolean().optional(),
      timezone: z.string().optional(),
    }),
});

const pages = defineCollection({
  loader: glob({ pattern: "**/[^_]*.{md,mdx}", base: "./src/content/pages" }),
  schema: z.object({
    title: z.string(),
    description: z.string().optional(),
    ogImage: z.string().optional(),
    canonicalURL: z.string().optional(),
  }),
});

export const collections = { posts, pages };
