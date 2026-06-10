import os
import socket
import ipaddress
from urllib.parse import urlparse

import httpx
import trafilatura
from fastmcp import FastMCP

mcp = FastMCP("smart-fetch")


def is_private_or_local_host(hostname: str) -> bool:
    if not hostname:
        return True

    hostname = hostname.strip().lower()

    if hostname in {"localhost", "0.0.0.0"}:
        return True

    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return True

    try:
        infos = socket.getaddrinfo(hostname, None)
        ips = {info[4][0].split("%")[0] for info in infos}
    except Exception:
        return False

    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return True
        except ValueError:
            continue

    return False


def extract_main_text(html: str, max_length: int = 4000) -> str:
    text = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=True,
        deduplicate=True,
        with_metadata=True,
    )

    if not text:
        return "⚠️ 未能提取到有效正文。"

    original_len = len(text)
    if len(text) > max_length:
        text = text[:max_length] + (
            f"\n\n---\n> ⚡ 原文约 {original_len} 字符，已截断到 {max_length} 字符。"
        )

    return f"📄 原文约 {original_len} 字符\n\n{text}"


@mcp.tool()
async def smart_fetch(url: str, max_length: int = 4000) -> str:
    """
    抓取网页正文，自动去掉导航/脚本/广告类噪声，并截断长度。
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "❌ URL 解析失败。"

    if parsed.scheme not in {"http", "https"}:
        return "❌ 只允许 http/https URL。"

    hostname = parsed.hostname
    if is_private_or_local_host(hostname or ""):
        return "🚫 安全限制：禁止访问内网、本机或保留地址。"

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=8.0),
            follow_redirects=True,
            headers={"User-Agent": "SmartFetchMCP/1.0 (+Render)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        return f"❌ 抓取失败：{e}"

    return extract_main_text(html, max_length=max_length)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port,
    )
