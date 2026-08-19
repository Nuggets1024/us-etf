// ETF 对比页 - 东财行情/净值代理（Cloudflare Worker 版）
// 静态页由 CF Pages 托管，本 Worker 只处理 /api/quote 与 /api/nav。

const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36";

function emHeaders(referer) {
  return {
    "User-Agent": UA,
    Referer: referer,
    Accept: "*/*",
    "Accept-Encoding": "gzip",
  };
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    try {
      if (path === "/api/quote") {
        return await apiQuote(url);
      }
      if (path === "/api/nav") {
        return await apiNav(url);
      }
      return new Response("not found", { status: 404 });
    } catch (ex) {
      return new Response(JSON.stringify({ error: String(ex) }), {
        status: 502,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
  },
};

async function apiQuote(url) {
  const secids = url.searchParams.get("secids");
  const fields = url.searchParams.get("fields");
  if (!secids) {
    return json({ error: "missing secids" }, 400);
  }
  const target =
    "https://push2delay.eastmoney.com/api/qt/ulist.np/get" +
    "?fltt=2&fields=" + encodeURIComponent(fields) +
    "&secids=" + encodeURIComponent(secids);

  const resp = await fetch(target, {
    headers: emHeaders("https://quote.eastmoney.com/"),
  });
  const body = await resp.arrayBuffer();
  return new Response(body, {
    status: resp.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

async function apiNav(url) {
  const code = url.searchParams.get("fundCode");
  const pageIndex = url.searchParams.get("pageIndex") || "1";
  const pageSize = url.searchParams.get("pageSize") || "3";
  if (!code) {
    return json({ error: "missing fundCode" }, 400);
  }
  const target =
    "https://api.fund.eastmoney.com/f10/lsjz" +
    "?fundCode=" + encodeURIComponent(code) +
    "&pageIndex=" + pageIndex +
    "&pageSize=" + pageSize;

  const resp = await fetch(target, {
    headers: emHeaders("https://fundf10.eastmoney.com/"),
  });
  const body = await resp.arrayBuffer();
  return new Response(body, {
    status: resp.status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}