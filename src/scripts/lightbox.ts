import { tplStr } from "@/i18n";

/*
  正文图片灯箱：点开正文里的图，铺满屏幕看大图。

  ── 一、为什么它从内联脚本搬到了这里 ──

  这段代码原来是 pages/posts/[...slug]/index.astro 里那个
  `<script is:inline data-astro-rerun>` 的一部分。is:inline 的意思是
  「原样抄进 HTML，不打包、不压缩、不去重」—— 于是这 8.4 KB 明文躺在
  **每一个文章页**的 HTML 里（当时整页 90 KB，它一个人占 9%）。文章越多，
  这份重复越贵，而且它每次都跟着 HTML 重新下载，享受不到任何缓存。

  搬成模块以后是一个带内容哈希的 .js：全站共用一份、压缩过、
  _headers 里 /_astro/* 那条 immutable 规则直接生效，第二个文章页起零下载。

  ── 二、桌面端为什么要单独补 ──

  原来的实现只有 touchstart/touchmove/touchend：双指缩放、双击放大、
  单指平移，手机上是完整的。桌面端**一个缩放入口都没有** —— 图片被
  max-h-[90dvh] 卡住就到头了，1472×1171 的 NERVA 试车台照片在 1080p 屏上
  照样看不清细节，而那恰好是这个站最需要放大的一类图。

  这里补的是滚轮缩放、单击逐档放大、拖拽平移，外加左右键在同一篇文章的
  图片间切换。触摸那套**原样保留、一行没动**：它已经调好了（缩放上限、
  双击 300ms 判定、平移边界），用 Pointer Events 重写成「一套代码管两端」
  听着更干净，实际是拿一个能用的东西去换回归风险。新代码只认 pointerType
  === "mouse"，和触摸路径互不相干。

  ── 三、桌面端为什么是单击放大，不是双击 ──

  一开始桌面端抄了触摸端的双击：1× ↔ 2× 来回切。实测下来两个毛病。

  一是它是**开关不是档位** —— 放大到 2× 之后再双击，图缩回 1× 而不是继续
  放大，「我想再看清楚一点」这个动作得到的是相反的结果。想到 4× 只能改用
  滚轮，而读者未必知道滚轮能缩放。

  二是**光标在说谎**：图上的光标一直是 zoom-in（放大镜），这是在明确承诺
  「点我会变大」，但当时单击**根本没有处理函数**，点下去什么都不发生。
  遮罩上同理，放大状态下光标是 zoom-out 却关不掉窗（见下面 click 处的守卫）。

  所以改成：单击 = 放大一档，到顶再点回到 1×；dblclick 处理函数直接删掉
  —— 双击自然会先派发两次 click，就是连放两档（1 → 2.56×），行为合理。
  **不要为了区分单双击加 250ms 延时**：那样每一次单击都会明显发粘，
  而这里单击是主交互，代价直接落在最常用的动作上。
  触摸端的双击开关保留不动，那在触屏上是通用惯例。
*/

type Strings = {
  /** 图片上的 aria-label，会拼上 alt */
  open: string;
  /** 对话框本身的 aria-label */
  dialog: string;
  close: string;
  prev: string;
  next: string;
  /** 第 {{index}} 张，共 {{total}} 张 */
  counter: string;
};

/*
  兜底文案。正常情况下用不到 —— 字符串由 index.astro 从 i18n 取好、
  塞在 #article 的 data-lightbox 上。这里留一份英文只是为了「JSON 没读到
  也不会渲染出 undefined」，不是第二套翻译，别在这儿加语言。
*/
const FALLBACK: Strings = {
  open: "Zoom image",
  dialog: "Image preview",
  close: "Close image preview",
  prev: "Previous image",
  next: "Next image",
  counter: "{{index}} / {{total}}",
};

const ZOOM_MIN = 1;
const ZOOM_MAX = 4;
/*
  桌面端单击放大一档的倍率。1 → 1.6 → 2.56 → 4（撞上限被夹住）→ 再点回 1×。
  三下到顶：档数太多要点半天，太少（比如 2×）就只剩一档中间态，失去「逐步
  逼近」的意义。触摸端双击仍然是 1 ↔ 2 的开关，不走这个常量。
*/
const ZOOM_CLICK_STEP = 1.6;
/*
  滚轮每一格的缩放倍率。1.0015 ^ deltaY —— 用指数而不是线性加法，
  是因为「从 1 到 2」和「从 2 到 4」在人眼里是同样大的一步。
  底数取这么小是因为不同设备的 deltaY 量级差得离谱（鼠标滚轮一格 100+，
  触控板惯性滚动一次 3~10），指数形式对两者都平滑。
*/
const ZOOM_WHEEL_BASE = 1.0015;
/*
  按下到松开的位移超过这个像素数，就判定成「拖拽」而不是「点击」。
  没有这道闸的话，在放大的图上拖到底松手会连带触发 click —— 而 click
  落在遮罩上就是关闭，读者刚拖到想看的位置，灯箱没了。
*/
const DRAG_SLOP = 4;

function readStrings(article: HTMLElement): Strings {
  const raw = article.dataset.lightbox;
  if (!raw) return FALLBACK;
  try {
    return { ...FALLBACK, ...(JSON.parse(raw) as Partial<Strings>) };
  } catch {
    return FALLBACK;
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function initLightbox(): void {
  const article = document.getElementById("article");
  if (!article) return;

  const strings = readStrings(article);

  const prefersReducedMotion = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let overlay: HTMLDivElement | null = null;
  let lastFocused: HTMLElement | null = null;

  /*
    可放大的图 = 正文里没有被 <a> 包住的 <img>。
    被链接包住的图点下去应该跳走，那是作者写链接时的意图，灯箱不抢。
  */
  const zoomableImages = (): HTMLImageElement[] =>
    Array.from(article.querySelectorAll("img")).filter(
      img => !img.closest("a")
    );

  /*
    推迟到下一帧再改属性。这些属性只影响无障碍树，不影响绘制，
    而首屏那张图的解码时间点是 LCP —— 在同一帧里同步改 DOM 会把它往后推。
    下面的事件是委托在 article 上的，不依赖这些属性先存在。
  */
  requestAnimationFrame(() => {
    for (const image of zoomableImages()) {
      image.setAttribute("role", "button");
      image.setAttribute("tabindex", "0");
      image.setAttribute("aria-haspopup", "dialog");
      image.setAttribute(
        "aria-label",
        image.alt ? `${strings.open}: ${image.alt}` : strings.open
      );
    }
  });

  function open(
    images: HTMLImageElement[],
    startIndex: number,
    trigger: HTMLElement | null
  ): void {
    if (overlay) return;
    lastFocused = trigger ?? (document.activeElement as HTMLElement | null);

    let index = startIndex;

    const el = document.createElement("div");
    overlay = el;
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.className =
      "fixed inset-0 z-50 flex cursor-zoom-out items-center justify-center bg-black/70 backdrop-blur-sm opacity-0 transition-opacity duration-200 motion-reduce:transition-none";

    const image = document.createElement("img");
    /*
      touch-none：把这张图上的默认触摸手势（浏览器自带的双指缩放、
      下拉刷新）交给我们自己的 touchmove 处理。不写的话在部分安卓浏览器上
      双指会同时触发页面级缩放和这里的缩放，画面直接打架。
      select-none：拖拽平移时不要顺手把图选中变成蓝色。
    */
    image.className =
      "max-h-[90dvh] max-w-[90dvw] object-contain touch-none select-none";
    image.draggable = false;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", strings.close);
    closeButton.className =
      "absolute end-4 top-4 rounded p-2 text-3xl leading-none text-white";
    closeButton.innerHTML = "&#10005;";
    closeButton.addEventListener("click", close);

    el.append(closeButton, image);

    /* ── 图片间切换。只有一张图时整套导航都不建 ── */
    const hasGallery = images.length > 1;
    let counter: HTMLDivElement | null = null;

    if (hasGallery) {
      counter = document.createElement("div");
      counter.className =
        "absolute inset-x-0 bottom-4 text-center text-sm text-white/80 tabular-nums";
      /* aria-live：读屏用户切图时需要被告知切到第几张了 */
      counter.setAttribute("aria-live", "polite");

      const navButton = (label: string, side: string, glyph: string) => {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("aria-label", label);
        button.className = `absolute ${side} top-1/2 -translate-y-1/2 rounded p-3 text-3xl leading-none text-white/80 hover:text-white`;
        button.innerHTML = glyph;
        return button;
      };

      const prevButton = navButton(strings.prev, "start-2", "&#10094;");
      const nextButton = navButton(strings.next, "end-2", "&#10095;");
      prevButton.addEventListener("click", () => step(-1));
      nextButton.addEventListener("click", () => step(1));

      el.append(prevButton, nextButton, counter);
    }

    function show(next: number): void {
      index = (next + images.length) % images.length;
      const source = images[index];
      if (!source) return;
      image.src = source.currentSrc || source.src;
      /*
        灯箱里的大图 alt 留空，是因为它和触发它的正文图是同一张 ——
        正文那张已经有 alt 了，这里再念一遍等于读屏用户听两遍。
        图的说明改由对话框自己的 aria-label 承担。
      */
      image.alt = "";
      el.setAttribute(
        "aria-label",
        source.alt ? `${strings.dialog}: ${source.alt}` : strings.dialog
      );
      if (counter) {
        counter.textContent = tplStr(strings.counter, {
          index: index + 1,
          total: images.length,
        });
      }
      resetTransform();
    }

    function step(delta: number): void {
      if (!hasGallery) return;
      show(index + delta);
    }

    /* ── 缩放与平移 ── */

    let currentScale = 1;
    let translateX = 0;
    let translateY = 0;

    // 触摸端状态（原实现，保持不动）
    let initialDist = 0;
    let initialScale = 1;
    let panStartX = 0;
    let panStartY = 0;
    let panStartTranslateX = 0;
    let panStartTranslateY = 0;
    let lastTapTime = 0;

    // 鼠标拖拽状态
    let dragging = false;
    let dragMoved = false;
    let suppressClick = false;

    function applyTransform(): void {
      image.style.transform = `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`;
      updateCursor();
    }

    function resetTransform(): void {
      currentScale = 1;
      translateX = 0;
      translateY = 0;
      image.style.transform = "";
      updateCursor();
    }

    /*
      光标就是这个灯箱唯一的操作说明 —— 没有工具栏，没有提示文字，读者靠
      它猜「这儿能干什么」。所以每一种形状都必须对应一个**真的会发生**的
      结果，这也是当初那个 bug 的教训（图上挂着放大镜却点不动）。

        grabbing  正在拖
        zoom-in   还没到顶，点一下再放大一档 —— 整个放大过程都显示它，
                  因为「还能接着点」正是这次要让读者发现的事
        grab      已到 ZOOM_MAX 且图溢出了视口：点已经没得放了，改提示能拖
        zoom-out  已到 ZOOM_MAX 但图根本没溢出（小图，比如 280px 的书封），
                  拖也没意义，那就提示再点一下回到原大小

      grab 的判定走 canPan() 而不是「scale > 1」：图小的时候放到 4× 也未必
      溢出视口，那种情况下 clampPan 会把平移量全夹成 0，显示 grab 等于又许
      了一个空头承诺 —— 和当初那个 bug 是同一种错。
    */
    function updateCursor(): void {
      if (dragging) image.style.cursor = "grabbing";
      else if (currentScale < ZOOM_MAX) image.style.cursor = "zoom-in";
      else image.style.cursor = canPan() ? "grab" : "zoom-out";

      /*
        遮罩：只有 1× 时点空白处才关得掉（原因见下面 click 监听）。放大之后
        清掉行内值，落回 className 里那条 cursor-zoom-out 之外的默认箭头。
      */
      el.style.cursor = currentScale <= ZOOM_MIN ? "" : "default";
    }

    /*
      平移的可用范围：图在缩放前的尺寸减去视口，多出来的一半就是能往每个
      方向拖的量；图没溢出就是 0。

      注意单位：transform 写的是 scale() 再 translate()，所以 translate 的
      数值是**缩放前**的像素。视口宽度换算过去就是 clientWidth / scale ——
      下面这两行除法就是干这个的，别照着屏幕像素改。
    */
    function panBounds(): { maxX: number; maxY: number } {
      return {
        maxX: Math.max(
          0,
          (image.clientWidth - el.clientWidth / currentScale) / 2
        ),
        maxY: Math.max(
          0,
          (image.clientHeight - el.clientHeight / currentScale) / 2
        ),
      };
    }

    /** 把平移量夹在「图不会被拖出视野」的范围里 */
    function clampPan(): void {
      const { maxX, maxY } = panBounds();
      translateX = clamp(translateX, -maxX, maxX);
      translateY = clamp(translateY, -maxY, maxY);
    }

    function canPan(): boolean {
      const { maxX, maxY } = panBounds();
      return maxX > 0 || maxY > 0;
    }

    /*
      以某个屏幕坐标为锚点缩放 —— 光标底下的那个点缩放前后要停在原地，
      否则滚轮放大时画面会往中心「跑」，想看的细节越放越偏。

      推导。变换写的是 scale(s)·translate(t)、origin 在中心，所以图上一点 p
      （缩放前坐标，相对中心量）落在屏幕的
          布局中心 + s·(p + t)
      设光标相对**布局中心**的偏移为 C，则当前 C = s·(p + t)，即 p = C/s − t。
      要求缩到 s′ 后这一点仍在 C 处：C = s′·(p + t′)，解得
          t′ = C/s′ − p = t + C·(1/s′ − 1/s)

      ⚠️ C 必须相对**布局中心**，不是 getBoundingClientRect 的中心。
      那个 rect 是变换后的盒子，它的中心 = 布局中心 + s·t —— 已经把 t 算进去
      了。直接拿它当基准，等于把 t 重复计了一次：t 为 0（未平移）时看不出来，
      一旦「已经放大并拖动过，再滚轮缩放」，图就会跳。所以下面补一项
      + currentScale * translateX 把布局中心还原回来。
      （这条是数值验证出来的，不是推出来的：把不变式代进去跑六组
      s/t/光标组合，漏掉这一项时漂移 30~75px，补上后是 0。）
    */
    function zoomAt(clientX: number, clientY: number, nextScale: number): void {
      const target = clamp(nextScale, ZOOM_MIN, ZOOM_MAX);
      if (target === currentScale) return;

      const rect = image.getBoundingClientRect();
      const offsetX =
        clientX - (rect.left + rect.width / 2) + currentScale * translateX;
      const offsetY =
        clientY - (rect.top + rect.height / 2) + currentScale * translateY;

      translateX += offsetX * (1 / target - 1 / currentScale);
      translateY += offsetY * (1 / target - 1 / currentScale);
      currentScale = target;

      if (currentScale === ZOOM_MIN) {
        resetTransform();
        return;
      }
      clampPan();
      applyTransform();
    }

    /* ── 桌面端输入 ── */

    el.addEventListener(
      "wheel",
      e => {
        /*
          passive: false + preventDefault：不拦的话滚轮会同时滚动
          遮罩后面的页面，关掉灯箱时人已经在另一个位置了。
        */
        e.preventDefault();
        zoomAt(
          e.clientX,
          e.clientY,
          currentScale * ZOOM_WHEEL_BASE ** -e.deltaY
        );
      },
      { passive: false }
    );

    /** 单击放大一档；已经到顶就回到 1× */
    function zoomStep(clientX: number, clientY: number): void {
      if (currentScale >= ZOOM_MAX) {
        resetTransform();
        return;
      }
      zoomAt(clientX, clientY, currentScale * ZOOM_CLICK_STEP);
    }

    /*
      记下最近一次按下用的是什么设备。触屏点一下也会补发一个 click（target
      同样是图片），不挡的话手机上轻点一次就跟着放大一档 —— 而触摸端本来
      有自己的双击开关，两套会打架：双击的第一下先派发 click 放到 1.6×，
      紧接着 touchstart 里的双击判定又把它设成 2×，中间闪一帧。
      触摸端的行为这次一点都不该变，所以在这儿拦住。

      判定写成「不是 touch」而不是「等于 mouse」：笔（pointerType 为 "pen"）
      不走 touchstart/touchmove 那套，把它一起排除掉的话手写笔用户就一个
      放大入口都没有了。默认值给 "mouse" 是兜底 —— 万一某处的 click 没有
      对应的 pointerdown（比如脚本派发的），宁可放大也不要点了没反应。
    */
    let lastPointerType = "mouse";
    el.addEventListener("pointerdown", e => {
      lastPointerType = e.pointerType;
    });

    image.addEventListener("pointerdown", e => {
      // 只管鼠标：触摸走上面那套 touch 事件，笔也不需要拖拽平移
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      if (currentScale <= ZOOM_MIN) return;
      dragging = true;
      dragMoved = false;
      panStartX = e.clientX;
      panStartY = e.clientY;
      panStartTranslateX = translateX;
      panStartTranslateY = translateY;
      image.setPointerCapture(e.pointerId);
      updateCursor();
    });

    image.addEventListener("pointermove", e => {
      if (!dragging) return;
      const dx = e.clientX - panStartX;
      const dy = e.clientY - panStartY;
      if (!dragMoved && Math.hypot(dx, dy) > DRAG_SLOP) dragMoved = true;
      translateX = panStartTranslateX + dx / currentScale;
      translateY = panStartTranslateY + dy / currentScale;
      clampPan();
      applyTransform();
    });

    function endDrag(e: PointerEvent): void {
      if (!dragging) return;
      dragging = false;
      if (image.hasPointerCapture(e.pointerId)) {
        image.releasePointerCapture(e.pointerId);
      }
      // 真拖动过就吃掉紧随其后的那次 click，别让它冒泡到遮罩去关窗
      suppressClick = dragMoved;
      updateCursor();
    }

    image.addEventListener("pointerup", endDrag);
    image.addEventListener("pointercancel", endDrag);

    /* ── 触摸端输入（原实现，未改动） ── */

    el.addEventListener(
      "touchstart",
      e => {
        const t = e.touches;
        if (t.length === 2) {
          initialDist = Math.hypot(
            t[1]!.clientX - t[0]!.clientX,
            t[1]!.clientY - t[0]!.clientY
          );
          initialScale = currentScale;
        } else if (t.length === 1) {
          const now = Date.now();
          if (now - lastTapTime < 300) {
            e.preventDefault();
            if (currentScale > 1) {
              resetTransform();
            } else {
              currentScale = 2;
              translateX = 0;
              translateY = 0;
              applyTransform();
            }
            lastTapTime = 0;
            panStartX = t[0]!.clientX;
            panStartY = t[0]!.clientY;
            panStartTranslateX = translateX;
            panStartTranslateY = translateY;
          } else {
            lastTapTime = now;
            if (currentScale > 1) {
              panStartX = t[0]!.clientX;
              panStartY = t[0]!.clientY;
              panStartTranslateX = translateX;
              panStartTranslateY = translateY;
            }
          }
        }
      },
      { passive: false }
    );

    el.addEventListener(
      "touchmove",
      e => {
        const t = e.touches;
        if (t.length === 2) {
          e.preventDefault();
          const dist = Math.hypot(
            t[1]!.clientX - t[0]!.clientX,
            t[1]!.clientY - t[0]!.clientY
          );
          currentScale = clamp(
            initialScale * (dist / initialDist),
            ZOOM_MIN,
            ZOOM_MAX
          );
          applyTransform();
        } else if (t.length === 1) {
          if (currentScale > 1) {
            e.preventDefault();
            translateX =
              panStartTranslateX + (t[0]!.clientX - panStartX) / currentScale;
            translateY =
              panStartTranslateY + (t[0]!.clientY - panStartY) / currentScale;
            clampPan();
            applyTransform();
          } else {
            e.preventDefault();
          }
        }
      },
      { passive: false }
    );

    const settleTouch = (e: TouchEvent) => {
      if (e.touches.length === 0 && currentScale <= 1.05) resetTransform();
    };
    el.addEventListener("touchend", settleTouch);
    el.addEventListener("touchcancel", settleTouch);

    /* ── 单击：图上放大，空白处关闭 ── */

    /*
      两件事合在**一个**监听器里，是因为它们共用 suppressClick 那道闸，
      而且 click 从图片冒泡到遮罩时会依次经过两处 —— 分开写就得约定谁先
      消费掉这个标志，多一个能踩的顺序坑。用 e.target 分派就没这问题：
      关闭按钮和左右翻页按钮各有自己的 handler，它们的 target 两个分支都
      不匹配，冒泡上来正好被忽略。

      放大状态下点空白**不关窗**（currentScale <= ZOOM_MIN 这道守卫）：
      放大之后遮罩上剩的空隙很窄，读者拖图看细节时手一滑就点在边上，
      窗一关重来一遍很恼人。要退出还有 Esc、右上角的 ×，以及先点回 1×。
    */
    el.addEventListener("click", e => {
      if (suppressClick) {
        suppressClick = false;
        return;
      }
      if (e.target === image) {
        if (lastPointerType !== "touch") zoomStep(e.clientX, e.clientY);
        return;
      }
      if (e.target === el && currentScale <= ZOOM_MIN) close();
    });

    show(index);

    document.body.appendChild(el);
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    requestAnimationFrame(() => overlay?.classList.add("opacity-100"));
    closeButton.focus();

    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") {
        close();
      } else if (e.key === "Tab") {
        trapFocus(e);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        step(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        step(1);
      }
    }

    function close(): void {
      if (!overlay) return;
      overlay = null;

      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
      lastFocused?.focus();
      lastFocused = null;

      if (prefersReducedMotion()) {
        el.remove();
        return;
      }
      const remove = () => el.remove();
      el.addEventListener("transitionend", remove, { once: true });
      setTimeout(remove, 250); // transitionend 没触发时的兜底
      el.classList.remove("opacity-100");
    }

    // 焦点关在对话框里，别让 Tab 跑到后面的页面上去
    function trapFocus(e: KeyboardEvent): void {
      const focusables = el.querySelectorAll<HTMLElement>(
        'a[href], button, [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;
      const first = focusables[0]!;
      const last = focusables[focusables.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  /*
    这两个写成箭头函数而不是 function 声明，是有原因的：函数声明会被提升到
    作用域顶部，于是 TypeScript 认为它「创建于 `if (!article) return` 之前」，
    捕获到的 article 仍是 HTMLElement | null，报 ts(18047)。
    箭头函数在原地创建，narrowing 带得进去。（上面 zoomableImages 同理。）
  */
  const triggerFromEvent = (e: Event): HTMLImageElement | null => {
    const image = (e.target as Element | null)?.closest("img");
    if (!(image instanceof HTMLImageElement)) return null;
    if (!article.contains(image) || image.closest("a")) return null;
    return image;
  };

  const activate = (image: HTMLImageElement): void => {
    const images = zoomableImages();
    const index = images.indexOf(image);
    open(images, index < 0 ? 0 : index, image);
  };

  article.addEventListener("click", e => {
    const image = triggerFromEvent(e);
    if (!image) return;
    e.preventDefault();
    activate(image);
  });

  article.addEventListener("keydown", e => {
    if (e.key !== "Enter" && e.key !== " " && e.key !== "Spacebar") return;
    const image = triggerFromEvent(e);
    if (!image) return;
    e.preventDefault();
    activate(image);
  });
}

initLightbox();
