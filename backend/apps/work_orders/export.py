import csv


def safe_csv_cell(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def csv_rows(queryset):
    class Echo:
        def write(self, value):
            return value
    writer = csv.writer(Echo())
    yield writer.writerow(["reference", "title", "status", "priority", "technician", "scheduled_start", "scheduled_end", "site_name"])
    for order in queryset.iterator(chunk_size=500):
        yield writer.writerow([
            safe_csv_cell(order.reference), safe_csv_cell(order.title), order.status, order.priority,
            safe_csv_cell(order.assigned_technician.get_username() if order.assigned_technician else ""),
            order.scheduled_start.isoformat() if order.scheduled_start else "",
            order.scheduled_end.isoformat() if order.scheduled_end else "",
            safe_csv_cell(order.site_name),
        ])
