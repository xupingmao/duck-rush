import os
import re
import argparse
from playwright.sync_api import sync_playwright, Page

# 全局缓存：记录图片url与二进制数据，去重
img_cache = {}
# 存储页面所有图片信息
img_meta_list = []
DEFAULT_TIMEOUT = 600_000

def capture_image_response(response):
    """监听网络响应，缓存图片二进制"""
    ct = response.headers.get("content-type", "")
    if ct.startswith("image/") and response.status == 200:
        url = response.url
        if url not in img_cache:
            try:
                img_cache[url] = response.body()
            except Exception:
                pass

def clean_filename(name: str) -> str:
    """清理Windows非法文件名字符"""
    return re.sub(r'[\\\/:*?"<>|]', "_", name.strip())

def scan_all_images(page: Page):
    """扫描页面所有img，收集元信息"""
    img_nodes = page.query_selector_all("img")
    for idx, node in enumerate(img_nodes):
        src = node.get_attribute("src") or node.get_attribute("data-src") or node.get_attribute("data-lazy")
        if not src:
            continue
        alt = node.get_attribute("alt") or f"img_{idx}"
        alt_clean = clean_filename(alt)
        # 判断图片是否加载完成
        loaded = node.evaluate("el => el.complete && el.naturalWidth > 0 && el.naturalHeight > 0")
        img_meta_list.append({
            "url": src,
            "alt_raw": alt,
            "filename_prefix": alt_clean,
            "loaded": loaded
        })

def main():
    parser = argparse.ArgumentParser(description="网页图片批量下载工具")
    parser.add_argument("target_url", type=str,
                        help="目标网页地址")
    parser.add_argument("--save-dir", "-o", type=str, default="./download_images",
                        help="图片保存目录 (默认: ./download_images)")
    args = parser.parse_args()

    target_url: str = args.target_url
    save_dir: str = args.save_dir
    os.makedirs(save_dir, exist_ok=True)

    with sync_playwright() as p:
        # 启动浏览器，可选关闭安全策略备用
        browser = p.chromium.launch(
            headless=False,
            # args=["--disable-web-security"]  # 如需彻底关闭CORS可打开此行
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 注册响应监听，捕获所有图片二进制
        page.on("response", capture_image_response)
        page.goto(target_url)
        
        input("> 加载完成后回车继续")
                
        print("页面加载完成，开始扫描图片...")

        # 扫描所有图片元数据
        scan_all_images(page)
        # URL去重
        unique_imgs = []
        seen_url = set()
        unloaded_list = []
        for meta in img_meta_list:
            if meta["url"] in seen_url:
                continue
            seen_url.add(meta["url"])
            if meta["loaded"]:
                unique_imgs.append(meta)
            else:
                unloaded_list.append(meta)

        print(f"\n==== 扫描结果 ====")
        print(f"有效已加载图片：{len(unique_imgs)} 张")
        print(f"未加载图片：{len(unloaded_list)} 张")
        if len(unloaded_list) > 0:
            print("未加载图片清单：")
            for item in unloaded_list:
                print(f"  URL: {item['url']} | Alt: {item['alt_raw']}")

        # 批量保存图片
        success = 0
        total = len(unique_imgs)
        for i, meta in enumerate(unique_imgs):
            url = meta["url"]
            prefix = meta["filename_prefix"]
            print(f"\r处理进度 {i+1}/{total} | 当前：{prefix}", end="")
            # 从缓存读取二进制
            if url not in img_cache:
                print(f"\n跳过 {prefix}：无缓存二进制")
                continue
            # 提取后缀
            ext = "jpg"
            if ".png" in url: ext = "png"
            elif ".gif" in url: ext = "gif"
            elif ".webp" in url: ext = "webp"
            save_path = os.path.join(save_dir, f"{prefix}.{ext}")
            with open(save_path, "wb") as f:
                f.write(img_cache[url])
            success += 1

        print(f"\n\n==== 下载完成汇总 ====")
        print(f"成功保存：{success} 张")
        print(f"未加载跳过：{len(unloaded_list)} 张")
        print(f"文件保存目录：{os.path.abspath(save_dir)}")
        browser.close()

if __name__ == "__main__":
    main()
