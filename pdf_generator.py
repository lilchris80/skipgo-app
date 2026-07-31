import base64
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

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

# The SkipGO logo, embedded directly so no separate image file is needed.
LOGO_B64 = """iVBORw0KGgoAAAANSUhEUgAAAfQAAAGdCAMAAADT83EqAAAA/1BMVEVgmF8jXiDt6aSSsZ/V6dzU2FxLc12TsSJhlyanyk7Q0iAtZUi41calzqPptR5RbxuQ
tlM2nTEljUWbwht2pYoLLgx7wTZ1wkncvEeKeBp9xpv9/f0EVykFSCX7wQetyiv7vQmUwy4GdzTM1ilztTAGZzBSpjMNhjQFRReJuy2wyRguljQEORa40Sv6
+dJpqy3I1Bf51FP31C731mopijNKmjLvxS/O5tYHOyMVkjYzZku70Rl0mIXtyU2rx7bx5pEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACRTAabAAAAQHRSTlP/////////////////////////////////////////////////////////////////////
////////////////73leyQAAYOJJREFUeNrtnYlC4srWqCsDECZBxL3Pf00MIGCQANqMIsL7v9WtVVOqkkoAG92tnTr79GBHwHxZ86pV6C5ff91C+S3Ioecr
h56vHHq+cuj5yqHnK4eerxx6vnLo+cqh5yuHnq8cer5y6PnKoecrh56vHHq+cuj5yqHn0POVQ89XDj1fOfR85dDzlUPPVw49Xzn0fOXQP33Zdk76b4Ju1yxU
NAwrR/23QLf3aOvdhmHgbXLqfwf0/a7qed5ms/Fc1zNyDf/zodtW1QPabhCGAD0s5rB/OPRau4oFHK8gCA0jwNC9MFfwPxq6tQUh98IwNBpOqdAMjCDwvGqu
4H8sdHtX3TARb5QKL4VfL04QNILA9XY57p8J3Sp6VKsbjWbh5Rdeq5dGYJQbIf6qXtTX9jqH/p2dt+0Ge20Blmwi45X7ewq98dI0Aq0vZ1vFqmcU1zn077nW
bSPEij0MDKf0goW8UqmsVljUC0ZQ+vXLCbGN38f9PWQQd++2mEP/lkE5MsLAw/EZVuuFwq97wI3FHP8PoFfuK/iJCIt2zBRgpe8S1x7l0L8f8iLV69h3eyGW
vFL59YthLwWNFdbzpduNHLbZzPoDdS/V3ufQ/2DkILIYOfbdXn6pC0MPS7/u7+8L2JfbeMx42+0qoY2derq8Yg79+znsIThvOuYvjdsC9uiwqOMHg/py9s4I
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
AAAASUVORK5CYII="""


def _get_logo_image():
    logo_bytes = base64.b64decode(LOGO_B64)
    return ImageReader(BytesIO(logo_bytes))


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

    # Logo, top-left. Aspect ratio matches the resized source image (500x413).
    logo = _get_logo_image()
    logo_w = 42 * mm
    logo_h = logo_w * (413 / 500)
    c.drawImage(
        logo, 15 * mm, page_height - 14 * mm - logo_h,
        width=logo_w, height=logo_h, mask="auto"
    )

    # Business details, top-right, right-aligned.
    text_x = page_width - 15 * mm
    y = page_height - 20 * mm
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(BRAND_GREEN)
    c.drawRightString(text_x, y, company.get("name", "SkipGO"))

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
    bar_y = page_height - 45 * mm
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


def generate_invoice_pdf(company, invoice, client, line_items):
    """
    Builds a branded PDF invoice.

    company:     dict from the 'companies' table (name, address, vat_number, settings)
    invoice:     dict from the 'invoices' table (invoice_number, issue_date, subtotal,
                 vat_rate, vat_amount, total_amount, status)
    client:      dict from the 'clients' table (name, address, phone)
    line_items:  list of dicts from 'invoice_line_items'
                 (description, quantity, unit_price, line_total)
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
    c.drawString(15 * mm, y, f"Date: {invoice['issue_date']}")
    y -= 10 * mm

    y = _draw_bill_to(c, client, 15 * mm, y)

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

    # Totals block, right-aligned
    totals_x_label = page_width - 65 * mm
    totals_x_value = page_width - 15 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(totals_x_label, y, "Net amount:")
    c.drawRightString(totals_x_value, y, f"EUR {float(invoice['subtotal']):.2f}")
    y -= 6 * mm
    c.drawString(totals_x_label, y, f"VAT ({invoice['vat_rate']}%):")
    c.drawRightString(totals_x_value, y, f"EUR {float(invoice['vat_amount']):.2f}")
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(BRAND_GREEN)
    c.drawString(totals_x_label, y, "Total:")
    c.drawRightString(totals_x_value, y, f"EUR {float(invoice['total_amount']):.2f}")

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
    c.drawString(15 * mm, y, f"Date: {quote.get('issue_date', '')}")
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
    y = y - table_height - 10 * mm

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(colors.grey)
    c.drawString(15 * mm, y, "This quote is valid for 14 days from the date above.")

    _draw_footer(c, page_width)
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.getvalue()