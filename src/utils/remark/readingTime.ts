/*
  统计正文字数、估算阅读时长，结果塞进 frontmatter 供页面读取。

  为什么不用现成的 reading-time / remark-reading-time：那些包按**空格分词**
  算 word count。中文不写空格，一整段两百字的中文在它们眼里是「1 个词」——
  算出来永远是「1 分钟」。对一个中文站来说这个数字不是不准，是没意义。

  所以这里自己数，而且分两种字符各按各的速度算：

    · 汉字/假名：按 400 字/分钟。中文阅读速度常见区间是 300–500，
      这个站是硬科幻科普，术语密度高，取中间偏保守的一档。
    · 拉丁词：按 200 词/分钟。同理，比通用的 250 慢一些 —— 正文里的拉丁
      词基本都是 delta-v、specific impulse 这类术语，不是流水句子。

    分钟数 = 汉字数 / 400 + 拉丁词数 / 200

  为什么在 remark 阶段做而不是渲染完再数 DOM：这里拿到的是 mdast，
  能精确挑出「真正会被读的文字」—— 链接地址、图片 alt、代码块都能按节点
  类型排除掉，而在 HTML 上做同样的事要先解析再过滤，还容易把图注、
  侧栏之类的东西数进去。而且这是构建期跑一次，运行时零开销。

  排除项（都是有意的）：
    · code —— 围栏代码块。读者是扫代码不是读代码，按字数计入会把时长撑得
      离谱。inlineCode 保留：那是句子的一部分（「把 `--base` 改掉」）。
    · html —— .md 里的原始 HTML 块。整块是标签文本，数进来全是噪音。
    · 图片 alt、链接 url —— 它们不是 text 节点，本来就走不到下面的 walk。
      （链接的**文字**是 link 的子 text 节点，会被正常计入，这是对的。）
*/

/*
  和 utils/rehype/ 那两个插件一样，只声明用得到的那几个字段，不引 @types/mdast。
  代价同样是这个类型比真实的 mdast 宽松，改这个文件时自己留神。
*/
type Node = {
  type: string;
  value?: string;
  children?: Node[];
};

type FileWithFrontmatter = {
  data?: {
    astro?: {
      frontmatter?: Record<string, unknown>;
    };
  };
};

/*
  汉字 + 日文假名。分四段：

    4E00–9FFF  CJK 统一表意文字（现代中文的绝大部分）
    3400–4DBF  扩展 A（生僻字，科幻文里偶尔有）
    F900–FAFF  兼容表意文字
    3040–30FF  平假名 + 片假名（引日文原文时用得上）

  **故意不含中文标点**（3000–303F、FF00–FF65）。标点不是「字」，
  数进去会让字数虚高 10% 上下，而且标点不占阅读时间。
*/
const CJK = /[一-鿿㐀-䶿豈-﫿぀-ヿ]/g;

/*
  拉丁词。带上 00C0–024F 是为了 Ariane、Tsiolkovsky 音译里可能出现的
  带音符字母；内部的撇号和连字符不断词，所以 delta-v 和 Clarke's 各算一个词。
*/
const LATIN_WORD = /[A-Za-z0-9À-ɏ]+(?:['’\-][A-Za-z0-9À-ɏ]+)*/g;

const CJK_PER_MINUTE = 400;
const LATIN_WORDS_PER_MINUTE = 200;

const SKIPPED = new Set(["code", "html", "yaml", "toml"]);

function collectText(node: Node, out: string[]): void {
  if (SKIPPED.has(node.type)) return;
  if (
    typeof node.value === "string" &&
    (node.type === "text" || node.type === "inlineCode")
  ) {
    out.push(node.value);
  }
  for (const child of node.children ?? []) collectText(child, out);
}

export function remarkReadingTime() {
  return (tree: Node, file: FileWithFrontmatter) => {
    const parts: string[] = [];
    collectText(tree, parts);
    const text = parts.join(" ");

    const cjkCount = text.match(CJK)?.length ?? 0;
    const latinCount = text.match(LATIN_WORD)?.length ?? 0;

    /*
      向上取整，并且保底 1 —— 「0 分钟读完」既没用又难看。
      空文章（还没写正文的草稿）也会显示 1 分钟，可以接受。
    */
    const minutes = Math.max(
      1,
      Math.ceil(cjkCount / CJK_PER_MINUTE + latinCount / LATIN_WORDS_PER_MINUTE)
    );

    /*
      字数取两者之和：中文读者看到的「字数」直觉上就是汉字数，
      而夹在里面的英文术语一个算一个词，加起来最接近那个直觉。
    */
    const frontmatter = file.data?.astro?.frontmatter;
    if (!frontmatter) return;

    frontmatter.readingTime = minutes;
    frontmatter.wordCount = cjkCount + latinCount;
  };
}
