import eslintPluginAstro from "eslint-plugin-astro";
import tsParser from "@typescript-eslint/parser";

export default [
  ...eslintPluginAstro.configs.recommended,
  {
    files: ["**/*.astro"],
    languageOptions: {
      parserOptions: {
        parser: tsParser,
      },
    },
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
    },
  },
  { rules: { "no-console": "error" } },
  // scripts/ 下是命令行工具，往终端打字就是它的本职工作
  { files: ["scripts/**"], rules: { "no-console": "off" } },
  { ignores: ["dist/**", ".astro/**", "public/pagefind/**"] },
];
