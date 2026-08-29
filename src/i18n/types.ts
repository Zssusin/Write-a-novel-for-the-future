export interface UIStrings {
  nav: {
    home: string;
    posts: string;
    tags: string;
    about: string;
    archives: string;
    search: string;
  };
  post: {
    publishedAt: string;
    updatedAt: string;
    /** 标题块里「CB-TM-YYYYMMDD」那格的标签 */
    docNo: string;
    /** 标题块里「N 字 · 约 M 分钟」那格的标签 */
    extent: string;
    sharePostIntro: string;
    sharePostOn: string;
    sharePostViaEmail: string;
    tagLabel: string;
    backToTop: string;
    goBack: string;
    editPage: string;
    previousPost: string;
    nextPost: string;
    seriesLabel: string;
    seriesProgress: string;
    partLabel: string;
    nextPart: string;
    translatedFrom: string;
    tableOfContents: string;
    listOfFigures: string;
    /** 约 {{minutes}} 分钟 —— 数字由 remarkReadingTime 估出来 */
    readingTime: string;
    /** {{count}} 字 */
    wordCount: string;
    comments: string;
  };
  /*
    正文图片灯箱。这几条只被 scripts/lightbox.ts 用到 —— 它是客户端模块，
    读不到 Astro 的 i18n，所以由文章页序列化成 JSON 塞在 #article 的
    data-lightbox 上传过去。加字段时两边要一起改。
  */
  lightbox: {
    /** 图片自身的 aria-label，后面会拼上 alt */
    open: string;
    /** 对话框的 aria-label */
    dialog: string;
    close: string;
    prev: string;
    next: string;
    /** 第 {{index}} 张，共 {{total}} 张 */
    counter: string;
  };
  pagination: {
    prev: string;
    next: string;
    page: string;
  };
  home: {
    socialLinks: string;
    featured: string;
    recentPosts: string;
    allPosts: string;
  };
  sidebar: {
    label: string;
    referenceLinks: string;
    allArchives: string;
    allTags: string;
  };
  footer: {
    copyright: string;
    allRightsReserved: string;
  };
  pages: {
    tagTitle: string;
    tagDesc: string;

    tagsTitle: string;
    tagsDesc: string;

    postsTitle: string;
    postsDesc: string;

    archivesTitle: string;
    archivesDesc: string;

    searchTitle: string;
    searchDesc: string;
  };
  a11y: {
    skipToContent: string;
    openMenu: string;
    closeMenu: string;
    toggleTheme: string;
    searchPlaceholder: string;
    noResults: string;
    goToPreviousPage: string;
    goToNextPage: string;
  };
  notFound: {
    title: string;
    message: string;
    goHome: string;
  };
}
