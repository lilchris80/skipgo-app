import os
from datetime import date
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

# The logo file must sit in the same folder as this script, named logo.jpg.
# Using os.path.dirname(__file__) means it loads correctly no matter what
# folder Streamlit happens to be running from.
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.jpg")

# ----------------------------------------------------------------
# BRAND SETTINGS
# Colours pulled directly from the SkipGO logo.
# ----------------------------------------------------------------
BRAND_GREEN = colors.HexColor("#035B2B")
BRAND_YELLOW = colors.HexColor("#FDC006")
BRAND_GREEN_LIGHT = colors.HexColor("#E8F5EC")

DEFAULT_PHONE = "77000006"
DEFAULT_EMAIL = "cyglobalimports@gmail.com"
DEFAULT_SERVICE_AREA = "Nicosia"


def fmt_date(value):
    """
    Converts a date (ISO string like '2026-08-03', or a real date object)
    into DD/MM/YYYY for display. Anything that isn't a real date (None,
    '?', 'still out', etc.) is returned unchanged.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%d/%m/%Y")


def _get_logo_image():
    return ImageReader(LOGO_PATH)


def _draw_header(c, company, doc_title, doc_number, page_width, page_height):
    """
    Draws the logo, business details, and coloured title banner at the
    top of the page. Returns the y position where the rest of the
    content should start being drawn, so nothing overlaps the header.
    """
    settings = company.get("settings") or {}
    phone = settings.get("phone", DEFAULT_PHONE)
    email = settings.get("email", DEFAULT_EMAIL)
    service_area = settings.get("service_area", DEFAULT_SERVICE_AREA)
    legal_name = settings.get("legal_name")

    # Logo, top-left. Aspect ratio matches the resized source image (500x413).
    logo = _get_logo_image()
    logo_w = 42 * mm
    logo_h = logo_w * (413 / 500)
    c.drawImage(
        logo, 15 * mm, page_height - 14 * mm - logo_h,
        width=logo_w, height=logo_h
    )

    # Business details, top-right, right-aligned.
    text_x = page_width - 15 * mm
    y = page_height - 20 * mm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(BRAND_GREEN)
    c.drawRightString(text_x, y, company.get("name", "SkipGO"))

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    if legal_name:
        y -= 4.5 * mm
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawRightString(text_x, y, legal_name)
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
    if company.get("vat_number"):
        y -= 5 * mm
        c.drawRightString(text_x, y, f"VAT No: {company['vat_number']}")
    y -= 5 * mm
    c.drawRightString(text_x, y, f"Tel: {phone}")
    y -= 5 * mm
    c.drawRightString(text_x, y, f"Email: {email}")
    y -= 5 * mm
    c.drawRightString(text_x, y, service_area)

    # Green/yellow divider bar under the header.
    bar_y = page_height - 50 * mm
    c.setFillColor(BRAND_GREEN)
    c.rect(0, bar_y, page_width, 2 * mm, fill=1, stroke=0)
    c.setFillColor(BRAND_YELLOW)
    c.rect(0, bar_y - 1 * mm, page_width, 1 * mm, fill=1, stroke=0)

    # Document title (INVOICE / QUOTE) and number.
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(BRAND_GREEN)
    c.drawString(15 * mm, bar_y - 13 * mm, doc_title)

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.black)
    c.drawString(15 * mm, bar_y - 20 * mm, doc_number)

    return bar_y - 28 * mm


def _draw_footer(c, page_width):
    """Thin brand-coloured strip at the very bottom of the page."""
    c.setFillColor(BRAND_GREEN)
    c.rect(0, 0, page_width, 3 * mm, fill=1, stroke=0)
    c.setFillColor(BRAND_YELLOW)
    c.rect(0, 3 * mm, page_width, 1 * mm, fill=1, stroke=0)

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(page_width / 2, 6 * mm, "Thank you for your business.")


def _draw_bill_to(c, client, x, y):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawString(x, y, "Bill To:")
    c.setFont("Helvetica", 10)
    y -= 5.5 * mm
    c.drawString(x, y, client.get("name", "Unknown client"))
    if client.get("address"):
        y -= 5.5 * mm
        c.drawString(x, y, client["address"])
    if client.get("phone"):
        y -= 5.5 * mm
        c.drawString(x, y, f"Tel: {client['phone']}")
    return y - 8 * mm


def _draw_rental_period(c, x, y, rental, invoice):
    """
    Draws a small section explaining the rental dates and, if relevant,
    how the late fee was calculated. Only draws anything if the invoice
    has this data saved on it (older invoices created before this feature
    won't have it, and are left alone rather than showing blank/wrong info).
    """
    if invoice.get("days_out") is None:
        return y

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawString(x, y, "Rental Period:")
    c.setFont("Helvetica", 10)
    y -= 5.5 * mm

    delivery = rental.get("start_date", "?") if rental else "?"
    pickup = rental.get("end_date") if rental else None
    if pickup:
        c.drawString(x, y, f"Delivery: {fmt_date(delivery)}    Pickup: {fmt_date(pickup)}")
    else:
        c.drawString(x, y, f"Delivery: {fmt_date(delivery)}    Pickup: still out at time of invoicing")
    y -= 5.5 * mm

    c.drawString(x, y, f"Total days rented: {invoice['days_out']}")
    y -= 5.5 * mm

    weeks_late = invoice.get("weeks_late") or 0
    late_fee = invoice.get("late_fee") or 0
    if weeks_late > 0:
        c.setFillColor(colors.HexColor("#B34700"))
        c.drawString(x, y, f"{weeks_late} week(s) over the free rental period — late fee: EUR {float(late_fee):.2f}")
        c.setFillColor(colors.black)
    else:
        c.drawString(x, y, "Within the free rental period — no late fee.")
    y -= 5.5 * mm

    return y - 3 * mm


def generate_invoice_pdf(company, invoice, client, line_items, rental=None):
    """
    Builds a branded PDF invoice.

    company:     dict from the 'companies' table (name, address, vat_number, settings)
    invoice:     dict from the 'invoices' table (invoice_number, issue_date, subtotal,
                 vat_rate, vat_amount, total_amount, status, and optionally
                 calculated_total, days_out, weeks_late, late_fee)
    client:      dict from the 'clients' table (name, address, phone)
    line_items:  list of dicts from 'invoice_line_items'
                 (description, quantity, unit_price, line_total)
    rental:      optional dict from the 'rentals' table (start_date, end_date) —
                 used to show the rental period section
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    y = _draw_header(
        c, company, "INVOICE", f"Invoice #{invoice['invoice_number']}",
        page_width, page_height
    )

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(15 * mm, y, f"Date: {fmt_date(invoice['issue_date'])}")
    y -= 10 * mm

    y = _draw_bill_to(c, client, 15 * mm, y)
    y = _draw_rental_period(c, 15 * mm, y, rental, invoice)

    # Line items table
    table_data = [["Description", "Qty", "Unit Price", "Line Total"]]
    for item in line_items:
        table_data.append([
            item["description"],
            str(item["quantity"]),
            f"EUR {float(item['unit_price']):.2f}",
            f"EUR {float(item['line_total']):.2f}",
        ])

    table = Table(table_data, colWidths=[85 * mm, 20 * mm, 35 * mm, 35 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_GREEN_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    table_width, table_height = table.wrap(0, 0)
    table.drawOn(c, 15 * mm, y - table_height)
    y = y - table_height - 8 * mm

    # Totals block, right-aligned. If the final amount was changed from the
    # calculated total (a discount or adjustment), show both so there's a
    # clear paper trail of what happened.
    totals_x_label = page_width - 90 * mm
    totals_x_value = page_width - 15 * mm
    total_amount = float(invoice["total_amount"])
    calculated_total = invoice.get("calculated_total")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)

    if calculated_total is not None and abs(float(calculated_total) - total_amount) > 0.01:
        diff = float(calculated_total) - total_amount
        c.drawString(totals_x_label, y, "Calculated total:")
        c.drawRightString(totals_x_value, y, f"EUR {float(calculated_total):.2f}")
        y -= 6 * mm
        if diff > 0:
            c.drawString(totals_x_label, y, "Discount:")
            c.drawRightString(totals_x_value, y, f"-EUR {diff:.2f}")
        else:
            c.drawString(totals_x_label, y, "Adjustment:")
            c.drawRightString(totals_x_value, y, f"+EUR {abs(diff):.2f}")
        y -= 8 * mm

    c.drawString(totals_x_label, y, "Net amount:")
    c.drawRightString(totals_x_value, y, f"EUR {float(invoice['subtotal']):.2f}")
    y -= 6 * mm
    c.drawString(totals_x_label, y, f"VAT ({invoice['vat_rate']}%):")
    c.drawRightString(totals_x_value, y, f"EUR {float(invoice['vat_amount']):.2f}")
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(BRAND_GREEN)
    c.drawString(totals_x_label, y, "Amount Charged:" if calculated_total is not None and abs(float(calculated_total) - total_amount) > 0.01 else "Total:")
    c.drawRightString(totals_x_value, y, f"EUR {total_amount:.2f}")

    _draw_footer(c, page_width)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()


def generate_quote_pdf(company, quote, client, size_label):
    """
    Builds a branded PDF quote.

    company:    dict from the 'companies' table
    quote:      dict from the 'quotes' table (quote_number, issue_date, quoted_price, status)
    client:     dict from the 'clients' table
    size_label: skip size label string, e.g. "6 Yard"
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    y = _draw_header(
        c, company, "QUOTE", f"Quote #{quote['quote_number']}",
        page_width, page_height
    )

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(15 * mm, y, f"Date: {fmt_date(quote.get('issue_date', ''))}")
    y -= 10 * mm

    y = _draw_bill_to(c, client, 15 * mm, y)

    table_data = [["Description", "Quoted Price (VAT incl.)"]]
    table_data.append([f"Skip rental - {size_label}", f"EUR {float(quote['quoted_price']):.2f}"])

    table = Table(table_data, colWidths=[110 * mm, 65 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    table_width, table_height = table.wrap(0, 0)
    table.drawOn(c, 15 * mm, y - table_height)
    y = y - table_height - 8 * mm

    if quote.get("free_days") is not None:
        c.setFont("Helvetica", 9.5)
        c.setFillColor(colors.black)
        c.drawString(
            15 * mm, y,
            f"Includes up to {quote['free_days']} days. After that: EUR {float(quote['weekly_late_rate']):.2f}/week until returned."
        )
        y -= 5 * mm
        c.drawString(
            15 * mm, y,
            "Replacing this skip with a new one at any time is charged again at the full quoted price above."
        )
        y -= 6 * mm

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(15 * mm, y, "This quote is valid for 14 days from the date above.")

    _draw_footer(c, page_width)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()