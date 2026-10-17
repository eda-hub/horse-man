"""削除した資料へのリンクを全MarkdownとHTMLから検査する。"""
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit, unquote

SOURCE_COMMIT = '885d7d490245ba4d948bb4594017371d17eadc04'
# Inline Markdown, reference-style Markdown, HTML href/src.
LINKS = re.compile(r'''(?P<md>!?\[[^\]\n]*\]\(\s*)(?P<target><[^>]+>|[^\s)]+)|(?P<ref>^\s*\[[^\]\n]+\]:\s*)(?P<ref_target><[^>]+>|\S+)|(?P<html>\b(?:href|src)\s*=\s*["'])(?P<html_target>[^"']+)|(?P<htmlbare>\b(?:href|src)\s*=\s*)(?P<htmlbare_target>[^\s"'>]+)''', re.M | re.I)


def local_target(root, source, target):
    target = unescape(target.strip('<>'))
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path)
    full = ((root / path.lstrip('/')) if path.startswith('/') else source.parent / path).resolve()
    try:
        return full.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def retarget(root, source, raw, deleted):
    text = raw.decode('utf-8',errors='surrogateescape')
    def replace(match):
        group = next(g for g in ('target', 'ref_target', 'html_target', 'htmlbare_target') if match.group(g) is not None)
        value = match.group(group)
        path = local_target(root, source, value)
        if path not in deleted:
            return match.group(0)
        parsed = urlsplit(value.strip('<>'))
        url = 'https://github.com/eda-hub/horse-man/blob/' + SOURCE_COMMIT + '/' + path
        if parsed.query: url += '?' + parsed.query
        if parsed.fragment: url += '#' + parsed.fragment
        if value.startswith('<'): url = '<' + url + '>'
        start, end = match.span(group)
        offset = match.start()
        return match.group(0)[:start-offset] + url + match.group(0)[end-offset:]
    return LINKS.sub(replace, text).encode('utf-8',errors='surrogateescape')


def verify_links(root, deleted):
    broken = []
    for source in root.rglob('*'):
        if '.git' in source.relative_to(root).parts or not source.is_file() or source.suffix.lower() not in {'.md', '.html', '.htm'}:
            continue
        text = source.read_text(encoding='utf-8',errors='surrogateescape')
        for match in LINKS.finditer(text):
            target = next(match.group(g) for g in ('target', 'ref_target', 'html_target', 'htmlbare_target') if match.group(g) is not None)
            if local_target(root, source, target) in deleted:
                broken.append(f'{source.relative_to(root)}:{text.count(chr(10),0,match.start())+1}: {target}')
    if broken:
        raise ValueError('削除済み資料へのリンク: ' + ' / '.join(broken))
