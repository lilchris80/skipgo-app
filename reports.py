import csv
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

BRAND_GREEN = colors.HexColor("#035B2B")
BRAND_GREEN_LIGHT = colors.HexColor("#E8F5EC")


def build_invoices_csv(invoices):
    """Builds a CSV file (as text) from a list of invoice dicts."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Invoice #", "Date", "Client", "Net (EUR)", "VAT (EUR)", "Total (EUR)", "Status"])
    for inv in invoices:
        client_name = inv["clients"]["name"] if inv.get("clients") else "Unknown"
        writer.writerow([
            inv["invoice_number"],
            inv["issue_date"],
            client_name,
            f"{float(inv['subtotal']):.2f}",
            f"{float(inv['vat_amount']):.2f}",
            f"{float(inv['total_amount']):.2f}",
            inv["status"],
        ])
    return output.getvalue()


def build_quotes_csv(quotes):
    """Builds a CSV file (as text) from a list of quote dicts."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Quote #", "Date", "Client", "Skip Size", "Quoted Price (EUR)", "Status"])
    for q in quotes:
        client_name = q["clients"]["name"] if q.get("clients") else "Unknown"
        size_label = q["skip_types"]["size_label"] if q.get("skip_types") else "?"
        writer.writerow([
            q["quote_number"],
            q.get("issue_date", ""),
            client_name,
            size_label,
            f"{float(q['quoted_price']):.2f}",
            q["status"],
        ])
    return output.getvalue()


def _build_report_pdf(title, company, table_header, table_rows, grand_total_label, grand_total_value, filter_description):
    """
    Shared builder for a paginating PDF report. Uses reportlab's Platypus
    engine (not the manual canvas approach used for single invoices/quotes)
    because a report can have hundreds of rows and needs automatic page
    breaks - Platypus handles that natively, manual canvas drawing does not.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=15 * mm, rightMargin=15 * mm
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"<b>{company.get('name', 'SkipGO')}</b>", styles["Title"]))
    elements.append(Paragraph(title, styles["Heading2"]))
    if filter_description:
        elements.append(Paragraph(filter_description, styles["Normal"]))
    elements.append(Spacer(1, 8 * mm))

    table_data = [table_header] + table_rows
    col_count = len(table_header)
    col_widths = [(180 * mm) / col_count] * col_count

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_GREEN),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_GREEN_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(f"<b>{grand_total_label}: EUR {grand_total_value:.2f}</b>", styles["Heading3"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_invoice_report_pdf(company, invoices, filter_description=""):
    rows = []
    grand_total = 0.0
    for inv in invoices:
        client_name = inv["clients"]["name"] if inv.get("clients") else "Unknown"
        rows.append([
            str(inv["invoice_number"]), inv["issue_date"], client_name,
            f"EUR {float(inv['total_amount']):.2f}", inv["status"]
        ])
        grand_total += float(inv["total_amount"])
    return _build_report_pdf(
        "Invoice Report", company,
        ["Invoice #", "Date", "Client", "Total", "Status"],
        rows, "Grand Total", grand_total, filter_description
    )


def generate_quote_report_pdf(company, quotes, filter_description=""):
    rows = []
    grand_total = 0.0
    for q in quotes:
        client_name = q["clients"]["name"] if q.get("clients") else "Unknown"
        size_label = q["skip_types"]["size_label"] if q.get("skip_types") else "?"
        rows.append([
            str(q["quote_number"]), q.get("issue_date", ""), client_name,
            size_label, f"EUR {float(q['quoted_price']):.2f}", q["status"]
        ])
        grand_total += float(q["quoted_price"])
    return _build_report_pdf(
        "Quote Report", company,
        ["Quote #", "Date", "Client", "Size", "Price", "Status"],
        rows, "Grand Total", grand_total, filter_description
    )