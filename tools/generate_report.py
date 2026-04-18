"""
tools/generate_report.py

World-class financial report PDF. Design principles:
  - Navy / amber / white palette — color used sparingly
  - Two-tone header with amber accent rule
  - KPI strip: 4 key metrics at a glance
  - Italic editorial intro with amber left bar
  - Numbered (01, 02 …) commentary bullets with hairline dividers
  - Clean matplotlib charts: white background, minimal grid
  - Yield snapshot + credit spreads tables in two-column layout
  - Compact data appendix, refined footer

Standalone test:
    python3 tools/generate_report.py
"""

import os
import subprocess
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, KeepInFrame, HRFlowable,
)

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY  = "#1B2A4A"
AMBER = "#E8820C"
TEAL  = "#2E8B8B"
RED   = "#C0392B"
LGRAY = "#E0E0E0"
MGRAY = "#888888"
DGRAY = "#2C2C2C"
ALT   = "#F6F6F6"

_NAVY  = colors.HexColor(NAVY)
_AMBER = colors.HexColor(AMBER)
_TEAL  = colors.HexColor(TEAL)
_RED   = colors.HexColor(RED)
_LGRAY = colors.HexColor(LGRAY)
_MGRAY = colors.HexColor(MGRAY)
_DGRAY = colors.HexColor(DGRAY)
_ALT   = colors.HexColor(ALT)
_WHITE = colors.white

TREASURY_SERIES     = ["DGS2", "DGS5", "DGS10", "DGS20", "DGS30"]
TREASURY_MATURITIES = [2, 5, 10, 20, 30]
SERIES_TO_MATURITY  = dict(zip(TREASURY_SERIES, TREASURY_MATURITIES))

PAGE_W, PAGE_H = letter
MARGIN    = 0.6 * inch
CONTENT_W = PAGE_W - 2 * MARGIN

_sty_counter = [0]
def _sty(base, **kw):
    _sty_counter[0] += 1
    return ParagraphStyle(f"{base}_{_sty_counter[0]}", **kw)


# ── Payload helpers ───────────────────────────────────────────────────────────
def _yield_current(yields: dict) -> dict:
    result = {}
    for sid, mat in SERIES_TO_MATURITY.items():
        d = yields.get(sid)
        if isinstance(d, dict):
            result[mat] = d.get("value")
    return result


def _yield_comparison(yields: dict, key: str) -> dict:
    block = yields.get(key, {})
    return {mat: block.get(sid) for sid, mat in SERIES_TO_MATURITY.items()}


def _week_range_label(week_ending: str) -> str:
    end   = date.fromisoformat(week_ending)
    start = end - timedelta(days=4)
    if start.month == end.month:
        return f"{start.strftime('%B %-d')} \u2013 {end.strftime('%-d, %Y')}"
    return f"{start.strftime('%B %-d')} \u2013 {end.strftime('%B %-d, %Y')}"


# ── Charts ────────────────────────────────────────────────────────────────────
def _clean_axes(ax, title: str):
    ax.set_facecolor("white")
    ax.set_title(title, fontsize=9, fontweight="bold", color=NAVY,
                 loc="left", pad=7)
    ax.grid(True, linestyle="-", color="#EEEEEE", linewidth=0.6, zorder=0)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["left", "bottom"]:
        ax.spines[sp].set_color(LGRAY)
        ax.spines[sp].set_linewidth(0.7)
    ax.tick_params(colors=MGRAY, labelsize=7.5, length=3, width=0.6)
    ax.xaxis.label.set_color(MGRAY)
    ax.xaxis.label.set_fontsize(8)
    ax.yaxis.label.set_color(MGRAY)
    ax.yaxis.label.set_fontsize(8)


def _yield_curve_chart(payload_yields: dict, output_path: str) -> str:
    friday  = payload_yields.get("week_ending", date.today().isoformat())
    fd      = date.fromisoformat(friday)
    ms_date = date(fd.year, fd.month, 1)
    ya_date = fd.replace(year=fd.year - 1)

    current = _yield_current(payload_yields)
    mstart  = _yield_comparison(payload_yields, "month_start")
    yr_ago  = _yield_comparison(payload_yields, "year_ago")

    def _v(d): return [d.get(m) for m in TREASURY_MATURITIES]

    cu_vals = _v(current)
    ms_vals = _v(mstart)
    ya_vals = _v(yr_ago)

    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    fig.patch.set_facecolor("white")

    ax.plot(TREASURY_MATURITIES, ya_vals, color="#CCCCCC",
            linewidth=1.1, linestyle="--",
            label=ya_date.strftime("%-m/%-d/%y"), zorder=2)
    ax.plot(TREASURY_MATURITIES, ms_vals, color=NAVY,
            linewidth=1.6, marker="o", markersize=3.5,
            label=ms_date.strftime("%-m/%-d/%y"), zorder=3)
    ax.plot(TREASURY_MATURITIES, cu_vals, color=AMBER,
            linewidth=2.2, marker="o", markersize=4.5,
            label=friday, zorder=4)

    valid_ms = [ms_vals[i] for i, m in enumerate(TREASURY_MATURITIES) if ms_vals[i] and cu_vals[i]]
    valid_cu = [cu_vals[i] for i, m in enumerate(TREASURY_MATURITIES) if ms_vals[i] and cu_vals[i]]
    valid_xs = [m for i, m in enumerate(TREASURY_MATURITIES) if ms_vals[i] and cu_vals[i]]
    if valid_xs:
        avg_diff = sum(c - m for c, m in zip(valid_cu, valid_ms)) / len(valid_xs)
        fill_c   = "#FDE8CC" if avg_diff > 0 else "#CCE8F0"
        ax.fill_between(valid_xs, valid_ms, valid_cu, alpha=0.3, color=fill_c, zorder=1)

    ax.set_xlabel("Maturity (Years)", labelpad=4)
    ax.set_ylabel("Yield (%)", labelpad=4)
    ax.set_xticks(TREASURY_MATURITIES)
    leg = ax.legend(loc="lower right", fontsize=7, frameon=True,
                    framealpha=0.95, edgecolor=LGRAY)
    leg.get_frame().set_linewidth(0.5)
    _clean_axes(ax, "U.S. Treasury Yield Curve")

    plt.tight_layout(pad=0.8)
    plt.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def _returns_chart(payload_returns: dict, output_path: str) -> str:
    sectors = [(k, v["value"]) for k, v in payload_returns.items()
               if isinstance(v, dict) and v.get("value") is not None]
    if not sectors:
        return output_path

    labels, values = zip(*sectors)
    n = len(sectors)
    fig, ax = plt.subplots(figsize=(3.4, max(1.8, n * 0.75)))
    fig.patch.set_facecolor("white")

    bar_colors = [TEAL if v >= 0 else RED for v in values]
    bars = ax.barh(list(labels), list(values), color=bar_colors,
                   height=0.45, edgecolor="none", zorder=3)

    for bar, val in zip(bars, values):
        offset = 0.012 if val >= 0 else -0.012
        ax.text(val + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:+.2f}%", va="center",
                ha="left" if val >= 0 else "right",
                fontsize=7.5, color=DGRAY, fontweight="bold", zorder=4)

    ax.axvline(0, color="#BBBBBB", linewidth=0.8, zorder=2)
    ax.set_xlabel("MTD Total Return (%)", labelpad=4)
    _clean_axes(ax, "Month-to-Date Returns")
    ax.tick_params(axis="y", labelsize=8)

    plt.tight_layout(pad=0.8)
    plt.savefig(output_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


# ── KPI strip ─────────────────────────────────────────────────────────────────
def _kpi_strip(payload_yields: dict, payload_spreads: dict) -> Table:
    current = _yield_current(payload_yields)
    mstart  = _yield_comparison(payload_yields, "month_start")

    def _yield_chg(mat):
        c, p = current.get(mat), mstart.get(mat)
        if c is None or p is None: return ""
        delta = round((c - p) * 100, 1)
        arrow, col = ("▲", RED) if delta > 0 else ("▼", TEAL)
        return f'<font color="{col}">{arrow} {abs(delta):.0f} bps MTD</font>'

    def _spread_chg(mtd):
        if mtd is None: return ""
        arrow, col = ("▲", RED) if mtd > 0 else ("▼", TEAL)
        return f'<font color="{col}">{arrow} {abs(mtd):.0f} bps MTD</font>'

    ig     = payload_spreads.get("IG_OAS", {})
    hy     = payload_spreads.get("HY_OAS", {})
    ig_val = ig.get("value") if isinstance(ig, dict) else None
    hy_val = hy.get("value") if isinstance(hy, dict) else None

    lbl_s = _sty("kl", fontSize=7,  leading=10, fontName="Helvetica",
                  textColor=_MGRAY, alignment=1)
    val_s = _sty("kv", fontSize=15, leading=19, fontName="Helvetica-Bold",
                  textColor=_NAVY,  alignment=1)
    chg_s = _sty("kc", fontSize=7.5, leading=10, fontName="Helvetica", alignment=1)

    def _cell(label, value, chg):
        return [Paragraph(label, lbl_s), Paragraph(value, val_s), Paragraph(chg, chg_s)]

    c10  = current.get(10)
    c2   = current.get(2)
    data = [[
        _cell("10yr Treasury",
              f"{c10:.2f}%" if c10 else "—", _yield_chg(10)),
        _cell("2yr Treasury",
              f"{c2:.2f}%"  if c2  else "—", _yield_chg(2)),
        _cell("IG OAS",
              f"{ig_val:.0f} bps" if ig_val else "—",
              _spread_chg(payload_spreads.get("IG_MTD_change"))),
        _cell("HY OAS",
              f"{hy_val:.0f} bps" if hy_val else "—",
              _spread_chg(payload_spreads.get("HY_MTD_change"))),
    ]]

    cw  = CONTENT_W / 4
    tbl = Table(data, colWidths=[cw] * 4)
    tbl.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE",    (0, 0), (0, 0), 3,   _AMBER),
        ("LINEABOVE",    (1, 0), (3, 0), 1.5, _NAVY),
        ("LINEAFTER",    (0, 0), (2, 0), 0.5, _LGRAY),
        ("BOX",          (0, 0), (-1, -1), 0.5, _LGRAY),
        ("BACKGROUND",   (0, 0), (-1, -1), _ALT),
    ]))
    return tbl


# ── Yield snapshot table ──────────────────────────────────────────────────────
def _yield_snapshot_table(payload_yields: dict) -> Table:
    current = _yield_current(payload_yields)
    mstart  = _yield_comparison(payload_yields, "month_start")

    hdr  = ["", "2yr", "5yr", "10yr", "20yr", "30yr"]
    row1 = ["Yield (%)"]
    row2 = ["MTD (bps)"]
    for m in TREASURY_MATURITIES:
        c, s = current.get(m), mstart.get(m)
        row1.append(f"{c:.2f}" if c is not None else "—")
        if c is not None and s is not None:
            d = round((c - s) * 100, 1)
            row2.append(f"+{d:.0f}" if d > 0 else f"{d:.0f}")
        else:
            row2.append("—")

    cw0 = 0.7 * inch
    cw  = (CONTENT_W / 2 - cw0) / len(TREASURY_MATURITIES)
    tbl = Table([hdr, row1, row2], colWidths=[cw0] + [cw] * len(TREASURY_MATURITIES))
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0), _WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",    (0, 1), (0, -1), _DGRAY),
        ("FONTSIZE",     (0, 0), (-1, -1), 7.5),
        ("ALIGN",        (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN",        (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND",   (0, 2), (-1, 2), _ALT),
        ("LINEBELOW",    (0, 0), (-1, 0), 0.5, _LGRAY),
        ("LINEBELOW",    (0, 1), (-1, 1), 0.3, _LGRAY),
        ("BOX",          (0, 0), (-1, -1), 0.4, _LGRAY),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


# ── Credit spreads table ──────────────────────────────────────────────────────
def _credit_spreads_table(payload_spreads: dict) -> Table:
    ig     = payload_spreads.get("IG_OAS", {})
    hy     = payload_spreads.get("HY_OAS", {})
    ig_val = ig.get("value") if isinstance(ig, dict) else None
    hy_val = hy.get("value") if isinstance(hy, dict) else None

    def _fmt(v):
        if v is None: return "—"
        return f"+{v:.0f}" if v > 0 else f"{v:.0f}"

    data = [
        ["Sector", "OAS (bps)", "MTD Chg"],
        ["IG Corporate", f"{ig_val:.0f}" if ig_val else "—",
         _fmt(payload_spreads.get("IG_MTD_change"))],
        ["HY Corporate", f"{hy_val:.0f}" if hy_val else "—",
         _fmt(payload_spreads.get("HY_MTD_change"))],
    ]

    col_w = CONTENT_W / 2 / 3
    tbl   = Table(data, colWidths=[col_w * 1.4, col_w * 0.8, col_w * 0.8])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0), _WHITE),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",     (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",    (0, 1), (0, -1), _DGRAY),
        ("FONTSIZE",     (0, 0), (-1, -1), 7.5),
        ("ALIGN",        (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN",        (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND",   (0, 2), (-1, 2), _ALT),
        ("LINEBELOW",    (0, 0), (-1, 0), 0.5, _LGRAY),
        ("LINEBELOW",    (0, 1), (-1, 1), 0.3, _LGRAY),
        ("BOX",          (0, 0), (-1, -1), 0.4, _LGRAY),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


# ── Data appendix ─────────────────────────────────────────────────────────────
def _appendix_rows(payload: dict) -> list[list]:
    rows = []
    yields  = payload.get("yields", {})
    spreads = payload.get("spreads", {})
    returns = payload.get("returns", {})

    for sid, mat in SERIES_TO_MATURITY.items():
        d = yields.get(sid, {})
        if isinstance(d, dict) and d.get("value"):
            rows.append([f"{mat}yr Treasury", f"{d['value']:.2f}%",
                         d.get("observation_date", ""), d.get("source", "")])

    for label, key in [("IG OAS", "IG_OAS"), ("HY OAS", "HY_OAS")]:
        d = spreads.get(key, {})
        if isinstance(d, dict) and d.get("value"):
            rows.append([label, f"{d['value']:.1f} bps",
                         d.get("observation_date", ""), d.get("source", "")])

    for sector, d in returns.items():
        if isinstance(d, dict) and d.get("value") is not None:
            rows.append([f"{sector} MTD Return", f"{d['value']:+.2f}%",
                         d.get("observation_date", ""), d.get("source", "")])
    return rows


# ── Section label helper ──────────────────────────────────────────────────────
def _section(text: str) -> list:
    s = _sty(f"sec", fontSize=7, leading=9, fontName="Helvetica-Bold",
              textColor=_MGRAY, spaceBefore=2, spaceAfter=4,
              letterSpacing=0.8)
    return [
        Paragraph(text.upper(), s),
        HRFlowable(width=CONTENT_W, thickness=0.5, color=_LGRAY,
                   spaceAfter=7, spaceBefore=0),
    ]


# ── Main PDF builder ──────────────────────────────────────────────────────────
def generate_report(payload: dict, narrative: dict, output_path: str) -> str:
    """
    Generate the weekly bond market PDF report.

    Args:
        payload:      Validated data payload
        narrative:    {"intro": str, "bullets": [{"text": str, "sub_bullets": [str]}]}
        output_path:  Destination path for the PDF

    Returns:
        output_path
    """
    payload_yields  = payload.get("yields",  {})
    payload_spreads = payload.get("spreads", {})
    payload_returns = payload.get("returns", {})
    week_ending     = payload.get("week_ending", date.today().isoformat())

    intro   = narrative.get("intro", "")
    bullets = narrative.get("bullets", [])

    yield_png   = "/tmp/bond_yield_curve.png"
    returns_png = "/tmp/bond_excess_returns.png"
    _yield_curve_chart(payload_yields, yield_png)
    _returns_chart(payload_returns, returns_png)

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=0.7 * inch,
    )
    story = []

    # ── Text styles ───────────────────────────────────────────────────────────
    intro_sty = _sty("intro", fontSize=9.5, leading=15,
                     fontName="Helvetica-Oblique", textColor=_DGRAY, alignment=4)
    body_sty  = _sty("body",  fontSize=9.5, leading=15,
                     fontName="Helvetica",         textColor=_DGRAY, alignment=4)
    mbul_sty  = _sty("mb",    fontSize=9.5, leading=15,
                     fontName="Helvetica",         textColor=_DGRAY, alignment=4,
                     leftIndent=22, firstLineIndent=0, spaceAfter=3)
    sbul_sty  = _sty("sb",    fontSize=8.5, leading=13,
                     fontName="Helvetica",         textColor=colors.HexColor("#555555"),
                     alignment=4, leftIndent=36, firstLineIndent=0, spaceAfter=3)

    # ── Header ────────────────────────────────────────────────────────────────
    sub_hdr = Table([[
        Paragraph(
            '<font color="#7A9BBF" size="7"><b>FIXED INCOME RESEARCH</b></font>',
            _sty("sh1", fontSize=7, fontName="Helvetica")),
        Paragraph(
            f'<font color="{AMBER}" size="7">{_week_range_label(week_ending)}</font>',
            _sty("sh2", fontSize=7, fontName="Helvetica", alignment=2)),
    ]], colWidths=[CONTENT_W * 0.55, CONTENT_W * 0.45])
    sub_hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
    ]))

    main_hdr = Table([[
        Paragraph(
            '<font color="white"><b>US Bond Market</b></font>'
            f'<font color="{AMBER}">  Weekly Update</font>',
            _sty("mh", fontSize=21, leading=27, fontName="Helvetica-Bold")),
    ]], colWidths=[CONTENT_W])
    main_hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    story.append(sub_hdr)
    story.append(main_hdr)
    story.append(HRFlowable(width=CONTENT_W, thickness=3.5, color=_AMBER,
                            spaceAfter=10, spaceBefore=0))

    # ── KPI strip ─────────────────────────────────────────────────────────────
    story.append(_kpi_strip(payload_yields, payload_spreads))
    story.append(Spacer(1, 0.15 * inch))

    # ── Word on the Desk ──────────────────────────────────────────────────────
    if intro:
        story.extend(_section("Word on the Desk"))
        intro_box = Table([[Paragraph(intro, intro_sty)]],
                          colWidths=[CONTENT_W - 14])
        intro_box.setStyle(TableStyle([
            ("LINEAFTER",    (0, 0), (0, -1), 3, _AMBER),
            ("LEFTPADDING",  (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]))
        story.append(intro_box)
        story.append(Spacer(1, 0.15 * inch))

    # ── Market Commentary ─────────────────────────────────────────────────────
    story.extend(_section("Market Commentary"))
    for i, b in enumerate(bullets, 1):
        num_para = Paragraph(
            f'<font color="{AMBER}"><b>{i:02d}</b></font>\u2002{b["text"]}',
            mbul_sty,
        )
        story.append(num_para)
        for sb in b.get("sub_bullets", []):
            story.append(Paragraph(f"\u2192\u2002{sb}", sbul_sty))
        if i < len(bullets):
            story.append(Spacer(1, 3))
            story.append(HRFlowable(
                width=CONTENT_W - 22, thickness=0.3, color=_LGRAY,
                spaceAfter=5, spaceBefore=0,
            ))

    story.append(Spacer(1, 0.18 * inch))

    # ── Market Data: two-column charts + tables ───────────────────────────────
    story.extend(_section("Market Data"))
    col_w = (CONTENT_W - 0.15 * inch) / 2

    left_items  = []
    right_items = []

    if os.path.exists(yield_png):
        left_items.append(Image(yield_png, width=col_w, height=col_w * 0.50))
    left_items.append(Spacer(1, 5))
    left_items.append(_yield_snapshot_table(payload_yields))

    if os.path.exists(returns_png):
        right_items.append(Image(returns_png, width=col_w, height=col_w * 0.68))
    right_items.append(Spacer(1, 5))
    right_items.append(_credit_spreads_table(payload_spreads))

    two_col = Table(
        [[KeepInFrame(col_w, 8 * inch, left_items,  mode="shrink"),
          KeepInFrame(col_w, 8 * inch, right_items, mode="shrink")]],
        colWidths=[col_w, col_w], hAlign="LEFT",
    )
    two_col.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ("LINEAFTER",    (0, 0), (0, -1), 0.5, _LGRAY),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 0.2 * inch))

    # ── Data Sources appendix ─────────────────────────────────────────────────
    app_rows = _appendix_rows(payload)
    if app_rows:
        story.extend(_section("Data Sources"))
        ap_data = [["Series", "Value", "As Of", "Source"]] + app_rows
        ap_tbl  = Table(ap_data,
                        colWidths=[1.5 * inch, 0.9 * inch, 1.1 * inch, 3.9 * inch])
        ap_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#3C3C3C")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), _WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 6.5),
            ("ALIGN",         (1, 0), (2, -1), "RIGHT"),
            ("LINEBELOW",     (0, 0), (-1, 0), 0.4, _LGRAY),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_WHITE, _ALT]),
            ("GRID",          (0, 0), (-1, -1), 0.25, _LGRAY),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ]))
        story.append(ap_tbl)

    # ── Footer ────────────────────────────────────────────────────────────────
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor(LGRAY))
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 0.52 * inch, PAGE_W - MARGIN, 0.52 * inch)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(MGRAY))
        canvas.drawString(MARGIN, 0.37 * inch,
                          "Sources: Federal Reserve (FRED), Tavily Web Search")
        canvas.drawString(MARGIN, 0.25 * inch,
                          f"For informational purposes only. Data as of {week_ending}.")
        canvas.drawRightString(PAGE_W - MARGIN, 0.37 * inch,
                               f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    today = date.today().isoformat()

    stub_payload = {
        "week_ending": today,
        "yields": {
            "week_ending": today,
            "DGS2":  {"value": 3.78, "observation_date": today, "source": "FRED:DGS2"},
            "DGS5":  {"value": 4.05, "observation_date": today, "source": "FRED:DGS5"},
            "DGS10": {"value": 4.32, "observation_date": today, "source": "FRED:DGS10"},
            "DGS20": {"value": 4.75, "observation_date": today, "source": "FRED:DGS20"},
            "DGS30": {"value": 4.93, "observation_date": today, "source": "FRED:DGS30"},
            "month_start": {"DGS2": 3.85, "DGS5": 4.12, "DGS10": 4.40,
                            "DGS20": 4.80, "DGS30": 4.98},
            "year_ago":    {"DGS2": 4.90, "DGS5": 4.70, "DGS10": 4.55,
                            "DGS20": 4.85, "DGS30": 4.95},
        },
        "spreads": {
            "IG_OAS":        {"value": 81.0,  "observation_date": today, "source": "FRED:BAMLC0A0CM"},
            "HY_OAS":        {"value": 286.0, "observation_date": today, "source": "FRED:BAMLH0A0HYM2"},
            "IG_MTD_change": -6.0,
            "HY_MTD_change": -30.0,
        },
        "returns": {
            "IG Corporates": {"value": 0.79, "observation_date": today, "source": "FRED:BAMLCC0A0CMTRIV"},
            "HY Corporates": {"value": 1.33, "observation_date": today, "source": "FRED:BAMLHYH0A0HYM2TRIV"},
        },
        "fed_speakers":         [],
        "late_breaking_events": [],
    }

    stub_narrative = {
        "intro": (
            "This week, the Treasury curve continued its gradual bull steepening as cooling inflation "
            "data reinforced the market's growing conviction that the Fed's next move is a cut. "
            "Investment-grade credit spreads reached their tightest levels since January, "
            "while high-yield posted its strongest monthly return in over a year. "
            "Portfolios positioned for duration extension and spread compression were rewarded."
        ),
        "bullets": [
            {
                "text": (
                    "The 10-year Treasury yield closed the week at 4.32%, down 8 bps from the prior "
                    "Friday, as softer-than-expected CPI data drove the largest single-week rate rally "
                    "since March. The 2s10s spread widened to 54 bps and the 2s30s spread reached "
                    "115 bps, marking a continued reversal of the prior bear flattening."
                ),
                "sub_bullets": [
                    "Month-to-date, the 10yr has rallied 8 bps from 4.40% at the start of April.",
                    "Real yields (10yr TIPS) fell to an estimated 1.85%, the lowest since mid-February.",
                ],
            },
            {
                "text": (
                    "IG Corporate OAS tightened 6 bps month-to-date to 81 bps — the tightest level "
                    "since January 2024 — supported by robust investor demand and below-average new "
                    "issuance. MTD total returns for IG Corporates stand at +0.79%, driven by the "
                    "combination of spread compression and the Treasury rally."
                ),
                "sub_bullets": [
                    "Weekly IG primary issuance was estimated at ~$18bn, well below the $25bn weekly average.",
                ],
            },
            {
                "text": (
                    "HY Corporate OAS tightened 30 bps month-to-date to 286 bps, reflecting strong "
                    "risk appetite and minimal near-term default concerns. HY Corporates returned "
                    "+1.33% MTD, outperforming every other major fixed income sector this month."
                ),
                "sub_bullets": [],
            },
            {
                "text": (
                    "No Fed officials made notable policy statements this week. The next scheduled "
                    "FOMC communication is the May 7 meeting, where markets are currently pricing "
                    "a hold with roughly 15% probability of a 25 bps cut."
                ),
                "sub_bullets": [],
            },
            {
                "text": (
                    "Oil prices remained range-bound near $82/bbl and trade policy uncertainty "
                    "continued to weigh on long-end demand, though no major geopolitical events "
                    f"materially disrupted market pricing in the week ending {today}."
                ),
                "sub_bullets": [],
            },
        ],
    }

    out = "/tmp/bond_report_test.pdf"
    generate_report(stub_payload, stub_narrative, out)
    print(f"PDF saved to {out}")
    subprocess.run(["open", out])
