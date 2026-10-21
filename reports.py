from io import BytesIO
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def make_pdf_report(summary, events_df, achievements_df, start_date, end_date):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4),
                            rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("COLLEGE SPORTS COORDINATION REPORT", styles["Title"]),
        Paragraph(f"Reporting period: {start_date} to {end_date}", styles["Normal"]),
        Paragraph(f"Generated: {date.today().isoformat()}", styles["Normal"]),
        Spacer(1, 8*mm), Paragraph("Summary", styles["Heading2"])
    ]
    rows = [["Metric", "Count"]] + [[str(k), str(v)] for k, v in summary.items()]
    table = Table(rows, colWidths=[100*mm, 35*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#183153")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), .4, colors.grey),
        ("PADDING", (0,0), (-1,-1), 6), ("VALIGN", (0,0), (-1,-1), "TOP")
    ]))
    story.extend([table, Spacer(1, 6*mm), Paragraph("Events in period", styles["Heading2"])])

    def add_data_table(df, columns, labels, widths):
        data = [labels]
        if df is None or df.empty:
            data.append(["No records in this period"] + [""] * (len(labels)-1))
        else:
            for _, row in df[columns].iterrows():
                data.append(["" if row[c] is None else str(row[c])[:90] for c in columns])
        table = Table(data, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#245b4a")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), .35, colors.grey),
            ("FONTSIZE", (0,0), (-1,-1), 8), ("PADDING", (0,0), (-1,-1), 5),
            ("VALIGN", (0,0), (-1,-1), "TOP")
        ]))
        return table

    story.append(add_data_table(
        events_df, ["event_date","event_name","sport","venue","status","result"],
        ["Date","Event","Sport","Venue","Status","Result"],
        [25*mm,48*mm,25*mm,42*mm,25*mm,55*mm]
    ))
    story.extend([Spacer(1,6*mm), Paragraph("Achievements in period", styles["Heading2"])])
    story.append(add_data_table(
        achievements_df, ["achievement_date","player_name","sport","achievement","competition"],
        ["Date","Player","Sport","Achievement","Competition"],
        [25*mm,38*mm,25*mm,60*mm,55*mm]
    ))
    doc.build(story)
    return output.getvalue()
