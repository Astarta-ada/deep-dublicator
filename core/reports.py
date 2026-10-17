"""Генерация отчётов: HTML и TXT."""

import datetime
import html
import logging
from pathlib import Path

from core.session import Session

log = logging.getLogger(__name__)


def _human_size(num: int) -> str:
    """Человекочитаемый размер."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def export_txt(session: Session, path: Path) -> None:
    """Экспорт отчёта в текстовом формате."""
    lines = [
        "Отчёт о дубликатах файлов",
        f"Дата: {session.created_at}",
        f"Автор: {session.created_by}",
        f"Директория: {session.root_scan_dir}",
        f"Фильтры: {session.filters}",
        f"Групп: {len(session.groups)}",
        "=" * 70,
        "",
    ]
    for i, g in enumerate(session.groups, 1):
        tag = " [ПУСТЫЕ]" if g.is_empty_group else ""
        lines.append(
            f"Группа #{i}{tag} — {len(g.files)} файлов, "
            f"{_human_size(g.size)} каждый"
        )
        for f in g.files:
            mark = "★" if f.is_original else " "
            lines.append(f"  {mark} {f.path}")
        lines.append("")

    Path(path).write_text("\n".join(lines), encoding="utf-8")
    log.info("TXT-отчёт сохранён: %s", path)


def export_html(session: Session, path: Path) -> None:
    """Экспорт отчёта в HTML."""
    rows: list[str] = []
    for i, g in enumerate(session.groups, 1):
        tag = " 🗂️ ПУСТЫЕ" if g.is_empty_group else ""
        rows.append(
            f"<h3>Группа #{i}{tag} "
            f"<small>({len(g.files)} файлов, "
            f"{_human_size(g.size)} каждый)</small></h3>"
        )
        rows.append('<table border="1" cellpadding="4" cellspacing="0">')
        rows.append(
            "<tr><th>Оригинал?</th><th>Путь</th>"
            "<th>Размер</th><th>Изменён</th></tr>"
        )
        for f in g.files:
            mark = "★" if f.is_original else ""
            mt = datetime.datetime.fromtimestamp(f.mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            rows.append(
                f"<tr><td align='center'>{mark}</td>"
                f"<td><code>{html.escape(f.path)}</code></td>"
                f"<td align='right'>{_human_size(f.size)}</td>"
                f"<td>{mt}</td></tr>"
            )
        rows.append("</table><br>")

    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Отчёт о дубликатах</title>
<style>
  body {{ font-family: sans-serif; margin: 24px; }}
  h1 {{ font-size: 20px; }}
  h3 {{ margin-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  code {{ font-size: 12px; }}
  small {{ color: #666; font-weight: normal; }}
</style>
</head><body>
<h1>Отчёт о дубликатах файлов</h1>
<p>
<b>Дата:</b> {html.escape(session.created_at)}<br>
<b>Автор:</b> {html.escape(session.created_by)}<br>
<b>Директория:</b> <code>{html.escape(session.root_scan_dir)}</code><br>
<b>Фильтры:</b> {html.escape(str(session.filters))}<br>
<b>Групп:</b> {len(session.groups)}
</p>
<hr>
{''.join(rows)}
</body></html>"""

    Path(path).write_text(doc, encoding="utf-8")
    log.info("HTML-отчёт сохранён: %s", path)


def export_deletion_list(session: Session, path: Path) -> None:
    """Список путей дубликатов (без оригиналов) — по одному в строке."""
    lines = []
    for g in session.groups:
        for f in g.files:
            if not f.is_original:
                lines.append(f.path)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    log.info("Список на удаление сохранён: %s (%d файлов)", path, len(lines))
