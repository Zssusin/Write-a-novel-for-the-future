// Place any global data in this file.
// You can import this data from anywhere in your site by using the `import` keyword.

export const SITE_TITLE = '飞向星空';
export const SITE_DESCRIPTION = '硬科幻爱好者的笔记：现实科技解读、原创故事、创作工具箱与书目推荐。';

export const CATEGORIES = [
	{ slug: 'sci-tech', label: '现实科技类' },
	{ slug: 'fiction', label: '原创故事' },
	{ slug: 'toolkit', label: '科幻作者工具箱' },
	{ slug: 'booklist', label: '书目推荐大全' },
] as const;

export type CategorySlug = (typeof CATEGORIES)[number]['slug'];

export function categoryLabel(slug: string): string {
	return CATEGORIES.find((c) => c.slug === slug)?.label ?? slug;
}
