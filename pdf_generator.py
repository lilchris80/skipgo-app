import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

# The logo file must sit in the same folder as this script, named logo.png.
# Using os.path.dirname(__file__) means it loads correctly no matter what
# folder Streamlit happens to be running from.
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

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