import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Question


def export_columns(event):
    """Active questions in form order, then removed questions that still hold answers."""
    active = list(event.questions.filter(is_archived=False))
    archived = list(event.questions.filter(is_archived=True))
    return active + archived


def column_title(q):
    return f"{q.label} (removed)" if q.is_archived else q.label


def _filename(event, ext):
    base = slugify(event.title)[:60] or "registrations"
    return f"{base}-registrations-{timezone.localdate():%Y-%m-%d}.{ext}"


def _typed(q, v):
    """Convert stored strings to real Excel types where it helps sorting/filtering."""
    if isinstance(v, list):
        return ", ".join(v)
    if v in ("", None):
        return None
    if q.qtype == Question.NUMBER:
        try:
            d = Decimal(v)
            return int(d) if d == d.to_integral() and abs(d) < 10**15 else float(d)
        except (InvalidOperation, ValueError):
            return v
    if q.qtype == Question.DATE:
        try:
            return date.fromisoformat(v)
        except ValueError:
            return v
    return v


def to_xlsx(event, submissions):
    cols = export_columns(event)
    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    ws.append([event.title])
    ws["A1"].font = Font(bold=True, size=14)
    sub = f"{submissions.count()} registration(s) · exported {timezone.localtime():%d %b %Y, %I:%M %p}"
    ws.append([sub])
    ws["A2"].font = Font(italic=True, color="666666")
    ws.append([])

    header_row = 4
    ws.append(["No.", "Registered at"] + [column_title(q) for q in cols])
    head_fill = PatternFill("solid", fgColor=event.accent.lstrip("#"))
    for c in ws[header_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = head_fill
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 30

    n = 0
    for s in submissions.order_by("number"):
        row = [s.number, timezone.localtime(s.created_at).replace(tzinfo=None)]
        row += [_typed(q, s.answers.get(str(q.id), "")) for q in cols]
        ws.append(row)
        r = ws.max_row
        ws.cell(r, 2).number_format = "DD-MMM-YYYY HH:MM"
        for i, q in enumerate(cols, start=3):
            cell = ws.cell(r, i)
            if q.qtype == Question.PHONE:
                cell.number_format = "@"
            elif q.qtype == Question.DATE and isinstance(cell.value, date):
                cell.number_format = "DD-MMM-YYYY"
            elif q.qtype == Question.LONG:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        n += 1

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 18
    for i, q in enumerate(cols, start=3):
        w = {Question.LONG: 40, Question.EMAIL: 28, Question.PHONE: 16, Question.MULTI: 30}.get(q.qtype, 22)
        ws.column_dimensions[get_column_letter(i)].width = max(w, min(len(column_title(q)) + 2, 40))
    ws.freeze_panes = ws.cell(header_row + 1, 3)
    last_col = get_column_letter(len(cols) + 2)
    ws.auto_filter.ref = f"A{header_row}:{last_col}{header_row + max(n, 1)}"

    # Summary sheet for choice questions
    choice_qs = [q for q in cols if q.qtype in Question.CHOICE_TYPES | {Question.YESNO}]
    if choice_qs:
        sm = wb.create_sheet("Summary")
        sm.column_dimensions["A"].width = 40
        sm.column_dimensions["B"].width = 12
        tallies = summarise(event, submissions, choice_qs)
        for q, rows, answered in tallies:
            sm.append([column_title(q)])
            sm.cell(sm.max_row, 1).font = Font(bold=True, size=12)
            sm.append(["Option", "Count"])
            for c in sm[sm.max_row]:
                c.font = Font(bold=True, color="FFFFFF")
                c.fill = head_fill
            for label, count, _pct in rows:
                sm.append([label, count])
            sm.append([f"Answered by {answered} of {n}"])
            sm.cell(sm.max_row, 1).font = Font(italic=True, color="666666")
            sm.append([])

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(event, "xlsx")}"'
    wb.save(resp)
    return resp


def to_csv(event, submissions):
    cols = export_columns(event)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(event, "csv")}"'
    resp.write("﻿")  # BOM so Excel reads UTF-8 (₦, accents) correctly
    w = csv.writer(resp)
    w.writerow(["No.", "Registered at"] + [column_title(q) for q in cols])
    for s in submissions.order_by("number"):
        w.writerow([s.number, timezone.localtime(s.created_at).strftime("%Y-%m-%d %H:%M")]
                   + [s.answer_for(q) for q in cols])
    return resp


def summarise(event, submissions, questions):
    """[(question, [(option, count, pct)], answered_count)] for choice questions."""
    out = []
    answers = list(submissions.values_list("answers", flat=True))
    for q in questions:
        key = str(q.id)
        counts = {o: 0 for o in q.choices}
        answered = 0
        for a in answers:
            v = a.get(key)
            if v in (None, "", []):
                continue
            answered += 1
            for item in (v if isinstance(v, list) else [v]):
                counts[item] = counts.get(item, 0) + 1  # keeps answers to since-renamed options
        rows = [(o, c, round(c * 100 / answered) if answered else 0) for o, c in counts.items()]
        out.append((q, rows, answered))
    return out
