"""
PDF請求書ジェネレーター
reportlab + HeiseiKakuGo-W5（内蔵CJKフォント）で日本語A4請求書を生成
"""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# =====================================================================
# 固定情報（ここを編集してカスタマイズしてください）
# =====================================================================
ISSUER = {
    "name": "株式会社サンプル",
    "address": "東京都○○区○○ 1-2-3",
    "contact": "担当者名　email@example.com",
    "reg_no": "登録番号：T1234567890123",
}

BANK_INFO = {
    "bank": "○○銀行（金融機関コード0000）",
    "branch": "○○支店（支店コード000）",
    "account": "普通 0000000",
    "holder": "カ）サンプル",
}
# =====================================================================

# コーポレートカラー (R, G, B) 0〜1 スケール
COLOR_RED = (0.72, 0.04, 0.08)
COLOR_BLACK = (0.10, 0.10, 0.10)
COLOR_WHITE = (1.0, 1.0, 1.0)
COLOR_GRAY_LIGHT = (0.95, 0.95, 0.95)
COLOR_GRAY_MID = (0.80, 0.80, 0.80)

FONT = "HeiseiKakuGo-W5"


def _register_fonts():
    """CJKフォント（reportlab内蔵）を登録"""
    pdfmetrics.registerFont(UnicodeCIDFont(FONT))


def _set_fill(c: canvas.Canvas, rgb: tuple):
    c.setFillColorRGB(*rgb)


def _set_stroke(c: canvas.Canvas, rgb: tuple):
    c.setStrokeColorRGB(*rgb)


def generate_invoice(data: dict, output_dir: str) -> tuple[str, str]:
    """
    請求書PDFを生成して (pdf_path, filename) を返す

    Args:
        data: Claude APIで解析した請求書データ
        output_dir: 出力先ディレクトリ
    Returns:
        (絶対パス, ファイル名)
    """
    _register_fonts()

    bill_to: str = data.get("bill_to", "")
    tax_included: bool = data.get("tax_included", False)
    items: list = data.get("items", [])
    due_date: str | None = data.get("due_date")
    invoice_number: str | None = data.get("invoice_number")
    notes: str | None = data.get("notes")

    # ------------------------------------------------------------------
    # 税計算
    # ------------------------------------------------------------------
    if tax_included:
        # 税込表示の場合：合計から逆算
        grand_total = sum(item["quantity"] * item["unit_price"] for item in items)
        tax = int(grand_total * 10 / 110)
        subtotal = grand_total - tax
    else:
        # 税抜の場合：小計に10%を加算
        subtotal = sum(item["quantity"] * item["unit_price"] for item in items)
        tax = int(subtotal * 0.1)
        grand_total = subtotal + tax

    # ------------------------------------------------------------------
    # ファイル名・パス
    # ------------------------------------------------------------------
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    filename = f"{bill_to}御中 ご請求書{date_str}.pdf"
    pdf_path = os.path.join(output_dir, filename)

    # ------------------------------------------------------------------
    # キャンバス初期化
    # ------------------------------------------------------------------
    w, h = A4  # 595.27, 841.89 pt
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setTitle(f"請求書 {date_str}")

    # ==================================================================
    # ヘッダー帯（黒）
    # ==================================================================
    header_h = 22 * mm
    _set_fill(c, COLOR_BLACK)
    c.rect(0, h - header_h, w, header_h, fill=1, stroke=0)

    # ロゴ画像（logo.png があれば左上に配置）
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        try:
            c.drawImage(
                logo_path,
                8 * mm,
                h - header_h + 3 * mm,
                height=16 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass  # ロゴ読み込み失敗は無視

    # 「請求書」白文字（右）
    _set_fill(c, COLOR_WHITE)
    c.setFont(FONT, 22)
    c.drawRightString(w - 15 * mm, h - header_h / 2 - 6, "請求書")

    # ==================================================================
    # 発行者情報（右寄せ）
    # ==================================================================
    y_right = h - header_h - 10 * mm
    c.setFont(FONT, 9)
    _set_fill(c, COLOR_BLACK)

    for line in [ISSUER["name"], ISSUER["address"], ISSUER["contact"]]:
        c.drawRightString(w - 15 * mm, y_right, line)
        y_right -= 5.5 * mm

    # 登録番号（赤）
    _set_fill(c, COLOR_RED)
    c.drawRightString(w - 15 * mm, y_right, ISSUER["reg_no"])

    # ==================================================================
    # 発行日・請求書番号・支払期限（左）
    # ==================================================================
    y_left = h - header_h - 10 * mm
    _set_fill(c, COLOR_BLACK)
    c.setFont(FONT, 9)

    c.drawString(15 * mm, y_left, f"発行日：{today.strftime('%Y年%m月%d日')}")
    y_left -= 5.5 * mm

    if invoice_number:
        c.drawString(15 * mm, y_left, f"請求書番号：{invoice_number}")
        y_left -= 5.5 * mm

    if due_date:
        # YYYY-MM-DD → YYYY年MM月DD日
        try:
            d = datetime.strptime(due_date, "%Y-%m-%d")
            due_str = d.strftime("%Y年%m月%d日")
        except ValueError:
            due_str = due_date
        c.drawString(15 * mm, y_left, f"お支払期限：{due_str}")

    # ==================================================================
    # 宛名（大きめ）＋ 赤い下線
    # ==================================================================
    y_bill = h - header_h - 50 * mm
    _set_fill(c, COLOR_BLACK)
    c.setFont(FONT, 18)
    bill_text = f"{bill_to}　御中"
    c.drawString(15 * mm, y_bill, bill_text)

    text_w = c.stringWidth(bill_text, FONT, 18)
    _set_stroke(c, COLOR_RED)
    c.setLineWidth(2)
    c.line(15 * mm, y_bill - 2, 15 * mm + text_w, y_bill - 2)

    # ==================================================================
    # ご請求金額ボックス（赤背景・白文字）
    # ==================================================================
    y_box_top = y_bill - 12 * mm
    box_h = 14 * mm
    _set_fill(c, COLOR_RED)
    c.rect(15 * mm, y_box_top - box_h, w - 30 * mm, box_h, fill=1, stroke=0)

    _set_fill(c, COLOR_WHITE)
    c.setFont(FONT, 10)
    c.drawString(20 * mm, y_box_top - box_h * 0.62, "ご請求金額（税込）")

    c.setFont(FONT, 17)
    c.drawRightString(w - 20 * mm, y_box_top - box_h * 0.68, f"¥ {grand_total:,}")

    # ==================================================================
    # 明細テーブル
    # ==================================================================
    y_table_top = y_box_top - box_h - 10 * mm
    row_h = 8 * mm

    # 列定義: (x起点, 幅, ヘッダー文字列, 数値列か)
    cols = [
        (15 * mm,  72 * mm, "品目",   False),
        (87 * mm,  22 * mm, "数量",   True),
        (109 * mm, 33 * mm, "単価",   True),
        (142 * mm, 33 * mm, "金額",   True),
    ]

    # ヘッダー行
    _set_fill(c, COLOR_BLACK)
    c.rect(15 * mm, y_table_top - row_h, w - 30 * mm, row_h, fill=1, stroke=0)
    _set_fill(c, COLOR_WHITE)
    c.setFont(FONT, 9)
    for x, cw, label, is_num in cols:
        if is_num:
            c.drawCentredString(x + cw / 2, y_table_top - row_h + 2.5 * mm, label)
        else:
            c.drawString(x + 2 * mm, y_table_top - row_h + 2.5 * mm, label)

    # データ行
    y_row = y_table_top - row_h
    for idx, item in enumerate(items):
        row_color = COLOR_GRAY_LIGHT if idx % 2 == 0 else COLOR_WHITE
        _set_fill(c, row_color)
        c.rect(15 * mm, y_row - row_h, w - 30 * mm, row_h, fill=1, stroke=0)

        amount = item["quantity"] * item["unit_price"]
        cells = [
            item.get("name", ""),
            str(item.get("quantity", "")),
            f"¥{item['unit_price']:,}",
            f"¥{amount:,}",
        ]
        _set_fill(c, COLOR_BLACK)
        c.setFont(FONT, 9)
        for (x, cw, _, is_num), cell_text in zip(cols, cells):
            if is_num:
                c.drawRightString(x + cw - 2 * mm, y_row - row_h + 2.5 * mm, cell_text)
            else:
                c.drawString(x + 2 * mm, y_row - row_h + 2.5 * mm, cell_text)

        y_row -= row_h

    # テーブル外枠（薄い罫線）
    _set_stroke(c, COLOR_GRAY_MID)
    c.setLineWidth(0.5)
    c.rect(15 * mm, y_row, w - 30 * mm, y_table_top - y_row, fill=0, stroke=1)

    # ==================================================================
    # 小計・消費税・合計
    # ==================================================================
    y_sub = y_row - 8 * mm
    label_x = 125 * mm
    value_x = w - 15 * mm

    _set_fill(c, COLOR_BLACK)
    c.setFont(FONT, 9)
    c.drawString(label_x, y_sub, "小計")
    c.drawRightString(value_x, y_sub, f"¥{subtotal:,}")
    y_sub -= 6.5 * mm

    tax_label = "消費税（10% 内税）" if tax_included else "消費税（10%）"
    c.drawString(label_x, y_sub, tax_label)
    c.drawRightString(value_x, y_sub, f"¥{tax:,}")
    y_sub -= 6.5 * mm

    # 区切り線
    _set_stroke(c, COLOR_GRAY_MID)
    c.setLineWidth(0.5)
    c.line(label_x, y_sub + 4, value_x, y_sub + 4)

    _set_fill(c, COLOR_RED)
    c.setFont(FONT, 11)
    c.drawString(label_x, y_sub, "合計（税込）")
    c.drawRightString(value_x, y_sub, f"¥{grand_total:,}")

    # ==================================================================
    # 備考
    # ==================================================================
    if notes:
        y_notes = y_sub - 12 * mm
        _set_fill(c, COLOR_BLACK)
        c.setFont(FONT, 9)
        c.drawString(15 * mm, y_notes, f"備考：{notes}")

    # ==================================================================
    # 振込先口座（黒背景・白文字）
    # ==================================================================
    bank_box_h = 28 * mm
    y_bank_top = 40 * mm
    _set_fill(c, COLOR_BLACK)
    c.rect(15 * mm, y_bank_top, w - 30 * mm, bank_box_h, fill=1, stroke=0)

    _set_fill(c, COLOR_WHITE)
    c.setFont(FONT, 9)
    line_gap = 5.5 * mm
    y_bl = y_bank_top + bank_box_h - 8 * mm
    c.drawString(20 * mm, y_bl, "【振込先】")
    y_bl -= line_gap
    c.drawString(20 * mm, y_bl, f"{BANK_INFO['bank']}　{BANK_INFO['branch']}")
    y_bl -= line_gap
    c.drawString(20 * mm, y_bl, f"口座種別・番号：{BANK_INFO['account']}")
    y_bl -= line_gap
    c.drawString(20 * mm, y_bl, f"口座名義：{BANK_INFO['holder']}")

    # ==================================================================
    # フッター帯（黒）
    # ==================================================================
    footer_h = 8 * mm
    _set_fill(c, COLOR_BLACK)
    c.rect(0, 0, w, footer_h, fill=1, stroke=0)
    _set_fill(c, COLOR_WHITE)
    c.setFont(FONT, 7)
    c.drawCentredString(w / 2, footer_h / 2 - 2, ISSUER["name"])

    # ==================================================================
    # 保存
    # ==================================================================
    c.save()
    return pdf_path, filename
