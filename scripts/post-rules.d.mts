/*
  post-rules.mjs 的类型声明。

  存在的唯一理由：tsconfig 继承 astro/tsconfigs/strict，allowJs 是关的，
  所以 src/content.config.ts 直接 import 那个 .mjs 会被 astro check 判成
  「找不到模块」。补这一份声明就够了 —— 比开 allowJs 干净，那个开关会把
  worker/index.js 也一起拖进 TS 的程序里（见那个文件顶部的注释）。

  给 post-rules.mjs 加导出时，这里要跟着加，否则新常量在 TS 那边不存在。
*/
export declare const POSTS_DIR: string;
export declare const UID_PATTERN: RegExp;
export declare const UID_HINT: string;
export declare const IMG_SIZE_IN_NAME: RegExp;
