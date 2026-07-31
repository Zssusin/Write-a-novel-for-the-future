const THEME_KEY = "theme";
const LIGHT = "light";
const DARK = "dark";

function getPreferredTheme(): string {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored) return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? DARK
    : LIGHT;
}

// Reuse the value already set by the inline FOUC-prevention script if available.
let themeValue: string =
  (window as unknown as { __theme?: { value: string } }).__theme?.value ??
  getPreferredTheme();

function persist(): void {
  localStorage.setItem(THEME_KEY, themeValue);
  reflect();
}

function reflect(): void {
  const root = document.firstElementChild;
  root?.setAttribute("data-theme", themeValue);
  root?.classList.toggle("dark", themeValue === DARK);
  document.querySelector("#theme-btn")?.setAttribute("aria-label", themeValue);

  // Fill <meta name="theme-color"> with the computed background colour so
  // Android's browser chrome matches the page background.
  const bg = window.getComputedStyle(document.body).backgroundColor;
  document
    .querySelector("meta[name='theme-color']")
    ?.setAttribute("content", bg);
}

function setup(): void {
  reflect();
  document.querySelector("#theme-btn")?.addEventListener("click", () => {
    themeValue = themeValue === LIGHT ? DARK : LIGHT;
    persist();
  });
}

setup();

// Re-run after View Transitions navigation.
document.addEventListener("astro:after-swap", setup);

// Carry the theme-color value across View Transitions to prevent the
// Android navigation bar from flashing during page transitions.
document.addEventListener("astro:before-swap", event => {
  const color = document
    .querySelector("meta[name='theme-color']")
    ?.getAttribute("content");
  if (color) {
    (event as { newDocument: Document }).newDocument
      .querySelector("meta[name='theme-color']")
      ?.setAttribute("content", color);
  }
});

/*
  跟随系统的明暗切换 —— 但**只在读者还没自己选过的时候**。

  localStorage 里有没有值，就是「读者选过没有」的唯一凭据：只有下面那个
  按钮的 click 处理器会写它（走 persist）。所以有值 = 手动点过。

  为什么要这条判断：原来这里无条件 persist()，于是「手动选浅色 → 晚上系统
  自动转深色」会让站跟着变深，**并且把那次明确选择覆盖掉** —— 读者第二天
  回来看到的还是深色，他那一次点击等于被系统抹掉了。明确的选择应当压过
  系统偏好，这是各家的通行做法。

  没选过的情况下走 reflect() 而不是 persist()：只更新当前这一屏，不落盘。
  一落盘就等于替读者做了选择，之后系统再变就跟不动了。
*/
window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", ({ matches }) => {
    if (localStorage.getItem(THEME_KEY)) return;
    themeValue = matches ? DARK : LIGHT;
    reflect();
  });
