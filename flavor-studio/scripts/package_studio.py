#!/usr/bin/env python3
"""Package the completed local studio without copying the source PDF.

Only the Python standard library is required. Assets must finish generating
before this script is run. Outputs are replaced atomically after validation.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

STUDIO = Path(__file__).resolve().parents[1]
WORKSPACE = STUDIO.parent
EXPECTED_INGREDIENTS = 1474
SINGLE_FILE = STUDIO / "风味创作室.html"
ZIP_FILE = WORKSPACE / "风味创作室_本地完整包.zip"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_local_file(relative: str, base: Path = STUDIO) -> Path:
    parts = urlsplit(unescape(relative))
    require(not parts.scheme and not parts.netloc, f"不支持外部资源：{relative}")
    resolved = (base / unquote(parts.path)).resolve()
    require(resolved.is_relative_to(STUDIO.resolve()), f"资源位于项目目录外：{relative}")
    require(resolved.suffix.lower() != ".pdf", "打包过程禁止复制原书 PDF")
    require(resolved.is_file(), f"资源不存在：{relative}")
    return resolved


def data_url(path: Path) -> str:
    mime = "image/svg+xml" if path.suffix.lower() == ".svg" else mimetypes.guess_type(path.name)[0]
    require(mime is not None, f"未知资源类型：{path.name}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def json_for_script(value: object) -> str:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def script_safe(source: str) -> str:
    return re.sub(r"</script", lambda match: "<\\/" + match.group(0)[2:], source, flags=re.I)


def inline_css_resources(css: str) -> str:
    def replace(match: re.Match) -> str:
        reference = match.group(2).strip()
        if reference.startswith(("data:", "#")):
            return match.group(0)
        return 'url("' + data_url(safe_local_file(reference)) + '")'
    require(not re.search(r"@import\b", css, re.I), "样式仍包含 @import，请先将依赖保存到本地")
    require(not re.search(r"</style", css, re.I), "样式中出现无法安全内联的结束标签")
    return re.sub(r"url\(\s*(['\"]?)(.*?)\1\s*\)", replace, css, flags=re.I)


class RuntimeReferenceCheck(HTMLParser):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"img", "script", "source", "iframe"} and values.get("src"):
            require(values["src"].startswith("data:"), f"单文件仍有外部运行资源：{values['src']}")
        if tag == "link" and values.get("rel") == "stylesheet":
            raise ValueError("单文件仍有未内联的样式表")


def make_single_file() -> dict:
    catalog = json.loads((STUDIO / "data/catalog.json").read_text(encoding="utf-8"))
    ingredients = catalog["ingredients"]
    require(len(ingredients) == EXPECTED_INGREDIENTS, "食材目录数量不是 1474，停止打包")
    ids = [ingredient["id"] for ingredient in ingredients]
    require(len(set(ids)) == EXPECTED_INGREDIENTS, "食材 ID 存在重复")
    expected_files = {f"{ingredient_id}.svg" for ingredient_id in ids}
    actual_files = {path.name for path in (STUDIO / "assets/ingredients").glob("*.svg")}
    require(actual_files == expected_files,
            f"食材 SVG 尚未齐全：缺少 {len(expected_files - actual_files)}，多出 {len(actual_files - expected_files)}")
    assets = {}
    for ingredient in ingredients:
        path = safe_local_file(f"assets/ingredients/{ingredient['id']}.svg")
        root = ET.fromstring(path.read_bytes())
        require(root.tag.split("}")[-1] == "svg", f"无效 SVG：{path.name}")
        for node in root.iter():
            for key, value in node.attrib.items():
                if key.split("}")[-1] == "href":
                    require(value.startswith(("#", "data:")), f"SVG 含有未内嵌资源：{path.name}")
        assets[ingredient["id"]] = data_url(path)
    manifest_path = STUDIO / "assets/manifest.json"
    require(manifest_path.is_file(), "图片资产目录 manifest.json 尚未生成")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    art_meta = {a["id"]:{"status":a["status"],"motif":a["motif"]} for a in manifest["assets"] if a["status"] != "illustrated"}
    (STUDIO / "data/art-meta.js").write_text("window.FLAVOR_ART_META=" + json_for_script(art_meta) + ";\n", encoding="utf-8")
    html = (STUDIO / "index.html").read_text(encoding="utf-8")
    css = inline_css_resources((STUDIO / "styles.css").read_text(encoding="utf-8"))
    data_js = (STUDIO / "data/data.js").read_text(encoding="utf-8")
    app_js = (STUDIO / "app.js").read_text(encoding="utf-8")
    art_meta_js = (STUDIO / "data/art-meta.js").read_text(encoding="utf-8")
    evidence_js = (STUDIO / "data/evidence-full.js").read_text(encoding="utf-8")
    engine_js = (STUDIO / "engine-full.js").read_text(encoding="utf-8")
    processing_data_js = (STUDIO / "data/processing-data.js").read_text(encoding="utf-8")
    processing_engine_js = (STUDIO / "processing-engine.js").read_text(encoding="utf-8")
    processing_ui_js = (STUDIO / "processing.js").read_text(encoding="utf-8")
    require("window.FLAVOR_DATA=" in data_js, "浏览器数据缺少 FLAVOR_DATA")
    html, styles_count = re.subn(
        r'<link\b(?=[^>]*\brel=[\"\']stylesheet[\"\'])(?=[^>]*\bhref=[\"\']styles\.css[\"\'])[^>]*>',
        lambda _: "<style>\n" + css + "\n</style>", html, flags=re.I)
    require(styles_count == 1, "未找到唯一的 styles.css 引用")
    for reference in ("data/data.js", "data/art-meta.js", "data/evidence-full.js", "engine-full.js", "data/processing-data.js", "processing-engine.js", "app.js", "processing.js"):
        pattern = r'<script\b(?=[^>]*\bsrc=[\"\']' + re.escape(reference) + r'[\"\'])[^>]*>\s*</script\s*>'
        html, count = re.subn(pattern, "", html, flags=re.I)
        require(count == 1, f"未找到唯一的脚本引用：{reference}")

    def inline_image(match: re.Match) -> str:
        src = match.group(3)
        embedded = src if src.startswith("data:") else data_url(safe_local_file(src))
        return match.group(1) + match.group(2) + escape(embedded, quote=True) + match.group(2)
    html = re.sub(r'(<img\b[^>]*\bsrc\s*=\s*)([\"\'])(.*?)(?:\2)', inline_image, html, flags=re.I)
    bootstrap = ("window.FLAVOR_ASSETS=" + json_for_script(assets) + ";\n"
                 "window.FLAVOR_ASSET_MANIFEST=" + json_for_script(manifest) + ";")
    # Inline scripts run synchronously: put them after the entire app DOM.
    scripts = "\n".join("<script>\n" + script_safe(source) + "\n</script>"
                        for source in (bootstrap, data_js, art_meta_js, evidence_js, engine_js, processing_data_js, processing_engine_js, app_js, processing_ui_js))
    require(len(re.findall(r"</body\s*>", html, re.I)) == 1, "页面缺少唯一的 body 结束标签")
    html = re.sub(r"</body\s*>", lambda _: scripts + "\n</body>", html, flags=re.I)
    RuntimeReferenceCheck().feed(html)
    require("assets/generated/strawberry-editorial.png" not in html.split("<script>")[0], "草莓首页图片未内嵌")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=STUDIO, prefix=".studio-", suffix=".tmp", delete=False) as f:
        temporary = Path(f.name)
        f.write(html)
    try:
        temporary.replace(SINGLE_FILE)
    finally:
        temporary.unlink(missing_ok=True)
    return {"ingredientSvgCount": len(assets), "singleHtmlBytes": SINGLE_FILE.stat().st_size,
            "nameReviewCards": sum(bool(item.get("nameNeedsReview")) for item in ingredients)}


def make_zip() -> int:
    files = [STUDIO / name for name in ("index.html", "styles.css", "app.js", "engine-full.js", "processing-engine.js", "processing.js", "风味创作室.html", "使用说明.txt")]
    for folder in ("data", "assets", "scripts"):
        files.extend(path for path in (STUDIO / folder).rglob("*") if path.is_file())
    included = []
    for path in sorted(set(files)):
        relative = path.relative_to(STUDIO)
        if any(part.lower() in {"qa", "__pycache__", "node_modules", ".git"} for part in relative.parts):
            continue
        if path.name == ".DS_Store" or path.suffix.lower() in {".pdf", ".pyc", ".tmp"}:
            continue
        require(path.resolve().is_relative_to(STUDIO.resolve()), f"不打包目录外符号链接：{relative}")
        require(path.is_file(), f"缺少交付文件：{relative}")
        included.append((path, str(Path("flavor-studio") / relative)))
    with tempfile.NamedTemporaryFile(dir=WORKSPACE, prefix=".flavor-studio-", suffix=".zip.tmp", delete=False) as f:
        temporary = Path(f.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path, archive_name in included:
                archive.write(path, archive_name)
        with zipfile.ZipFile(temporary) as archive:
            require(archive.testzip() is None, "压缩包完整性验证失败")
            require(not any(name.lower().endswith(".pdf") for name in archive.namelist()), "压缩包禁止包含原书 PDF")
        temporary.replace(ZIP_FILE)
    finally:
        temporary.unlink(missing_ok=True)
    return len(included)


def main() -> None:
    result = make_single_file()
    result.update({"archiveFiles": make_zip(), "html": str(SINGLE_FILE), "zip": str(ZIP_FILE),
                   "zipBytes": ZIP_FILE.stat().st_size, "sourcePdfCopied": False})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
