"""Генерация отчётов: HTML и TXT."""

import datetime
import html
import logging
from pathlib import Path

from core.session import Session
from utils.helpers import human_size

log = logging.getLogger(__name__)


def export_txt(session: Session, path: Path):  # -> None:
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
            f"{human_size(g.size)} каждый"
        )
        for f in g.files:
            mark = "★" if f.is_original else " "
            lines.append(f"  {mark} {f.path}")
        lines.append("")

    Path(path).write_text("\n".join(lines), encoding="utf-8")
    log.info("TXT-отчёт сохранён: %s", path)


def export_html(session: Session, path: Path):  # -> None:
    """Экспорт отчёта в HTML."""
    rows: list[str] = []
    for i, g in enumerate(session.groups, 1):
        tag = " 🗂️ ПУСТЫЕ" if g.is_empty_group else ""
        rows.append(
            f"<h3>Группа #{i}{tag} "
            f"<small>({len(g.files)} файлов, "
            f"{human_size(g.size)} каждый)</small></h3>"
        )
        rows.append('<table border="1" cellpadding="4" cellspacing="0">')
        rows.append(
            "<tr><th>Оригинал?</th><th>Путь</th>"
            "<th>Размер</th><th>Изменён</th></tr>"
        )
        for f in g.files:
            mark = "★" if f.is_original else ""
            # Конвертируем timestamp в строку
            mt = datetime.datetime.fromtimestamp(f.mtime).strftime(
                "%Y-%m-%d %H:%M"
            )
            rows.append(
                f"<tr><td align='center'>{mark}</td>"
                f"<td><code>{html.escape(f.path)}</code></td>"
                f"<td align='right'>{human_size(f.size)}</td>"
                f"<td>{mt}</td></tr>"
            )
        rows.append("</table><br>")

    # Формируем итоговый HTML-документ
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Отчёт о дубликатах</title>
<style>
  body {{ font-family: sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
  h1 {{ font-size: 20px; color: #2563eb; }}
  h3 {{ margin-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; background: white; border-color: #e2e8f0; }}
  th {{ background: #f1f5f9; padding: 8px; text-align: left; }}
  td {{ padding: 8px; }}
  code {{ font-size: 12px; color: #475569; }}
  small {{ color: #64748b; font-weight: normal; }}
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


def export_deletion_list(session: Session, path: Path):  # -> None:
    """Список путей дубликатов (без оригиналов) — по одному в строке."""
    lines = []
    for g in session.groups:
        for f in g.files:
            if not f.is_original:
                lines.append(f.path)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    log.info("Список на удаление сохранён: %s (%d файлов)", path, len(lines))
