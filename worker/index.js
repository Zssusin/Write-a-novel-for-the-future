/*
  把 R2 桶挂到自己站点的 /img/ 路径下。

  为什么不直接用 R2 的公开地址（pub-xxxx.r2.dev）：
  那个地址会被**写死在每篇文章的 markdown 里**。以后绑了自己的域名，
  或者换了桶，每一篇引用过图片的文章都要改一遍。走 /img/ 的话文章里写的是
  相对路径，域名换成什么都不用动正文。（Cloudflare 自己也说 r2.dev 有限速、
  不建议用于正式环境。）

  这个文件是**纯静态站的唯一例外**。wrangler.jsonc 里的 run_worker_first
  只把 /img/* 交给它，其余路径直接由资源层发出，不经过这里、没有冷启动。

  故意用 .js 而不是 .ts：tsconfig 继承的是 astro/tsconfigs/strict 且没开
  allowJs，所以这个文件不进 astro check 的类型检查 —— 也就不需要为了
  env.IMG 的类型专门装 @cloudflare/workers-types。少一个依赖。
*/

const PREFIX = "/img/";

/*
  浏览器缓存 7 天。故意不加 immutable、也不用一年：
  那样的话你哪天用同一个文件名换了张图，旧图会在读者浏览器里留一年。
  7 天之后浏览器会带 If-None-Match 来问一次，没变就是一个 304，很便宜。

  规矩：**要换内容就换文件名。** R2 出站免费，多存一个文件不花钱。
*/
const CACHE_CONTROL = "public, max-age=604800";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    /*
      理论上只有 /img/* 会进来。但静态资源没命中时 Worker 也会被叫醒
      （Workers 的资源层就是这么设计的），那种情况把请求交回资源层，
      让它按 not_found_handling 发 404 页面。
    */
    if (!url.pathname.startsWith(PREFIX)) {
      return env.ASSETS.fetch(request);
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed", {
        status: 405,
        headers: { allow: "GET, HEAD" },
      });
    }

    // /img/2026/foo.webp → 2026/foo.webp，就是 R2 里的对象名
    const key = decodeURIComponent(url.pathname.slice(PREFIX.length));

    // 空 key 会让 R2 报错；".." 挡掉试探性的路径穿越
    if (!key || key.includes("..")) {
      return new Response("Not Found", { status: 404 });
    }

    // onlyIf 把请求里的 If-None-Match 等条件头交给 R2 自己判断
    const object = await env.IMG.get(key, { onlyIf: request.headers });

    if (object === null) {
      return new Response("Not Found", { status: 404 });
    }

    const headers = new Headers();
    // 把上传时记录的 content-type 等元数据写回响应
    object.writeHttpMetadata(headers);
    headers.set("etag", object.httpEtag);
    headers.set("cache-control", CACHE_CONTROL);

    /*
      条件不满足时 R2 返回的是一个没有 body 的对象 —— 意思是「内容没变」。
      判断依据是有没有 body 这个属性，不是 body 是不是 null。
    */
    if (!("body" in object)) {
      return new Response(null, { status: 304, headers });
    }

    return new Response(object.body, { headers });
  },
};
