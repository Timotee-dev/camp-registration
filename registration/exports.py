import csv

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = [
    "Reg Code", "First Name", "Last Name", "Gender", "Phone", "Email",
    "Arrival Date", "Special Needs", "Registered At", "Email Status", "SMS Status",
]


def _rows(qs):
    for a in qs:
        yield [
            a.reg_code, a.first_name, a.last_name, a.get_gender_display(), a.phone_display,
            a.email, a.arrival_date, a.special_needs,
            timezone.localtime(a.created_at).replace(tzinfo=None),
            a.email_status, a.sms_status,
        ]


def _filename(event, ext):
    return f"{slugify(event.name)}-attendees-{timezone.localdate():%Y%m%d}.{ext}"


def to_csv(event, qs):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(event, "csv")}"'
    resp.write("﻿")  # BOM so Excel opens UTF-8 correctly
    w = csv.writer(resp)
    w.writerow(HEADERS)
    for row in _rows(qs):
        row[6] = row[6].strftime("%Y-%m-%d")
        row[8] = row[8].strftime("%Y-%m-%d %H:%M")
        # Keep Excel from turning phone numbers into numbers (dropping the leading 0).
        row[4] = f"'{row[4]}"
        w.writerow(row)
    return resp


def to_xlsx(event, qs):
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendees"

    ws.append([f"{event.name} — Attendee List"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"{event.venue} · {event.start_date:%d %b} – {event.end_date:%d %b %Y} · "
               f"exported {timezone.localtime():%d %b %Y %H:%M}"])
    ws["A2"].font = Font(italic=True, color="666666")
    ws.append([])

    header_row = 4
    ws.append(HEADERS)
    fill = PatternFill("solid", fgColor="1F4E3D")
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center")

    count = 0
    for row in _rows(qs):
        ws.append(row)
        r = ws.max_row
        ws.cell(r, 5).number_format = "@"
        ws.cell(r, 7).number_format = "DD-MMM-YYYY"
        ws.cell(r, 9).number_format = "DD-MMM-YYYY HH:MM"
        ws.cell(r, 8).alignment = Alignment(wrap_text=True, vertical="top")
        count += 1

    widths = [12, 16, 16, 9, 15, 28, 14, 40, 18, 13, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(header_row + 1, 1)
    if count:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(HEADERS))}{header_row + count}"

    # Summary sheet
    s = wb.create_sheet("Summary")
    s.append(["Metric", "Count"])
    for c in s[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
    first, last = header_row + 1, header_row + max(count, 1)
    s.append(["Total attendees", count])
    s.append(["Male", f'=COUNTIF(Attendees!D{first}:D{last},"Male")'])
    s.append(["Female", f'=COUNTIF(Attendees!D{first}:D{last},"Female")'])
    s.append(["With special needs", f'=COUNTIF(Attendees!H{first}:H{last},"?*")'])
    s.append([])
    s.append(["Arrival date", "Arrivals"])
    for c in s[s.max_row]:
        c.font = Font(bold=True)
    days = sorted({a.arrival_date for a in qs})
    for d in days:
        s.append([d, f"=COUNTIF(Attendees!G{first}:G{last},A{s.max_row + 1})"])
        s.cell(s.max_row, 1).number_format = "DD-MMM-YYYY"
    s.column_dimensions["A"].width = 22
    s.column_dimensions["B"].width = 12

    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{_filename(event, "xlsx")}"'
    wb.save(resp)
    return resp
