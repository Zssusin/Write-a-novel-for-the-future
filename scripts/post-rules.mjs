/*
  文章规则的单一出处。

  这里只放**两边都要用**的东西：schema（src/content.config.ts）和构建前的
  校验脚本（scripts/check-posts.mjs）。以前这些常量两边各写一份，改一处忘
  一处的后果是安静的 —— 要么后台存得进去、构建才炸，要么脚本放行、schema 拦下。

  故意是 .mjs：check-posts.mjs 由 `node` 直接跑，不经过任何构建，只能吃 JS。
  让它读 .ts 得靠 Node 的类型剥离，那要求的版本比 package.json 里写的
  22.12 高 —— 为一个正则赌运行环境不划算。
  代价是旁边要有一份 post-rules.d.mts，理由写在那个文件里。

  还有第三处也在重复这些规则：public/admin/config.yml 里的后台表单。
  那一份共享不了（它是浏览器读的 YAML，没有 import），只能靠约定：
  改完那个文件，本地跑一次 npm run build。
*/

/** 文章目录，相对仓库根。改这里要同时确认 public/admin/config.yml 的 folder。 */
export const POSTS_DIR = "src/content/posts";

/*
  uid 的形状：8–40 位，首位小写字母，其余字母、数字或连字符。

  首位必须是字母，这不是审美 —— 全是数字的 uid（比如 00000000）会被 YAML
  解析成数字而不是字符串，报出来的是 "Expected string, received number"，
  从这句话根本看不出是 frontmatter 的问题。让首位永远是字母，
  这种情况按构造就不可能出现。熵还是够：26 × 36^7 ≈ 2×10^12。

  长度放宽到 8–40、允许大写和连字符，是为了同时容纳两种来源：

    npm run uid                    → 8 位，手写文章用，短、好认
    后台（Sveltia CMS 的 uuid 组件）→ 27 位，形如 uC5T6KX3M6N7G4Y2Z1A0B9C8D7E
                                     浏览器里跑不了 npm，只能让它自己生成

  两种都是「创建时生成一次，之后永不改动」—— 对 uid 来说这才是关键性质。
  为什么需要这么一个键，见 src/content.config.ts 里 uid 字段上面那段。
*/
export const UID_PATTERN = /^[a-z][0-9a-zA-Z-]{7,39}$/;

/** 格式不对时给人看的那句话。schema 和脚本共用，省得两边措辞不一样。 */
export const UID_HINT =
  "uid 要 8–40 位：首位小写字母，其余字母、数字或连字符。用 `npm run uid` 生成，或由后台自动生成";
