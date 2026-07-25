"""
python-docxで議事録Wordファイルを生成するモジュール。
AIには触らせず、このモジュールだけが様式を制御する。
"""

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor, Cm


# ===== スタイル定数 =====
COLOR_HEADER_BG = RGBColor(0x1F, 0x49, 0x7D)   # 濃紺
COLOR_SECTION_BG = RGBColor(0xBD, 0xD7, 0xEE)  # 薄青
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_BLACK = RGBColor(0x00, 0x00, 0x00)
FONT_NAME_JP = "游明朝"
FONT_NAME_JP_FALLBACK = "MS Mincho"


def _set_cell_bg(cell, color: RGBColor):
    """セルの背景色を設定する。"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    hex_color = f"{color[0]:02X}{color[1]:02X}{color[2]:02X}"
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def _set_font(run, size_pt: int, bold: bool = False, color: RGBColor = COLOR_BLACK):
    """runのフォントを設定する。"""
    run.font.name = FONT_NAME_JP
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = color
    # 日本語フォント設定
    r = run._r
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:eastAsia"), FONT_NAME_JP)
    rPr.insert(0, rFonts)


def _add_section_heading(doc: Document, text: str):
    """セクション見出しを追加する（薄青背景の1列テーブル）。"""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    _set_cell_bg(cell, COLOR_SECTION_BG)
    para = cell.paragraphs[0]
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = para.add_run(f"■ {text}")
    _set_font(run, 11, bold=True, color=COLOR_BLACK)
    doc.add_paragraph()


def _add_bullet(doc: Document, text: str, indent: int = 0):
    """箇条書きを追加する。"""
    para = doc.add_paragraph()
    para.paragraph_format.left_indent = Cm(indent * 0.5 + 0.5)
    run = para.add_run(f"・{text}")
    _set_font(run, 10)
    para.paragraph_format.space_after = Pt(2)


def build_minutes_docx(data: dict) -> bytes:
    """
    議事録データ（dict）からWordファイルを生成してバイト列で返す。

    Args:
        data: extract_minutes()が返す構造化データ

    Returns:
        .docxファイルのバイト列
    """
    doc = Document()

    # ===== 用紙・余白設定 =====
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.0)

    # ===== タイトル =====
    title_table = doc.add_table(rows=1, cols=1)
    title_table.style = "Table Grid"
    title_cell = title_table.cell(0, 0)
    _set_cell_bg(title_cell, COLOR_HEADER_BG)
    title_para = title_cell.paragraphs[0]
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meeting_name = data.get("meeting_name", "会議") or "会議"
    title_run = title_para.add_run(f"{meeting_name}　議事録")
    _set_font(title_run, 16, bold=True, color=COLOR_WHITE)

    doc.add_paragraph()

    # ===== 基本情報テーブル =====
    info_table = doc.add_table(rows=3, cols=2)
    info_table.style = "Table Grid"
    info_table.columns[0].width = Cm(3.5)
    info_table.columns[1].width = Cm(13.0)

    info_rows = [
        ("開催日時", data.get("date", "") or ""),
        ("参加者", "、".join(data.get("participants", [])) or ""),
        ("作成日", datetime.now().strftime("%Y年%m月%d日")),
    ]

    for i, (label, value) in enumerate(info_rows):
        label_cell = info_table.cell(i, 0)
        value_cell = info_table.cell(i, 1)
        _set_cell_bg(label_cell, COLOR_SECTION_BG)

        label_para = label_cell.paragraphs[0]
        label_run = label_para.add_run(label)
        _set_font(label_run, 10, bold=True)

        value_para = value_cell.paragraphs[0]
        value_run = value_para.add_run(value)
        _set_font(value_run, 10)

    doc.add_paragraph()

    # ===== 議題ごとの議論内容 =====
    agenda_items = data.get("agenda_items", [])
    if agenda_items:
        _add_section_heading(doc, "議題・議論内容")
        for item in agenda_items:
            title = item.get("title", "")
            discussion = item.get("discussion", "")

            # 議題タイトル
            title_para = doc.add_paragraph()
            title_para.paragraph_format.left_indent = Cm(0.5)
            title_para.paragraph_format.space_before = Pt(4)
            title_run = title_para.add_run(f"▶ {title}")
            _set_font(title_run, 10, bold=True)

            # 議論内容
            disc_para = doc.add_paragraph()
            disc_para.paragraph_format.left_indent = Cm(1.0)
            disc_para.paragraph_format.space_after = Pt(6)
            disc_run = disc_para.add_run(discussion)
            _set_font(disc_run, 10)

        doc.add_paragraph()

    # ===== 決定事項 =====
    decisions = data.get("decisions", [])
    _add_section_heading(doc, "決定事項")
    if decisions:
        for d in decisions:
            _add_bullet(doc, d)
    else:
        _add_bullet(doc, "（なし）")
    doc.add_paragraph()

    # ===== 次回議題・日程 =====
    _add_section_heading(doc, "次回議題・日程")

    next_date = data.get("next_date", "") or ""
    if next_date:
        date_para = doc.add_paragraph()
        date_para.paragraph_format.left_indent = Cm(0.5)
        date_run = date_para.add_run(f"次回開催：{next_date}")
        _set_font(date_run, 10, bold=True)

    next_topics = data.get("next_topics", [])
    if next_topics:
        for t in next_topics:
            _add_bullet(doc, t)
    else:
        _add_bullet(doc, "（なし）")

    # ===== フッター =====
    doc.add_paragraph()
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer_run = footer_para.add_run("以上")
    _set_font(footer_run, 10)

    # バイト列として返す
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


if __name__ == "__main__":
    # POC③: サンプルデータでWord生成確認
    sample_data = {
        "meeting_name": "第3回プロジェクト定例",
        "date": "2026年07月25日 14:00",
        "participants": ["田中", "山田", "佐藤"],
        "agenda_items": [
            {
                "title": "前回アクションの確認",
                "discussion": "山田より仕様書が80%完成していることを報告。今週中に完成予定。"
            },
            {
                "title": "システム設計について",
                "discussion": "データベースはPostgreSQLを採用することで合意。パフォーマンス要件を満たすと判断。"
            },
            {
                "title": "開発環境の決定",
                "discussion": "開発環境はDockerで統一することに決定。各メンバーの環境差異を解消する。"
            }
        ],
        "decisions": [
            "データベースはPostgreSQLを採用する",
            "開発環境はDockerで統一する"
        ],
        "next_topics": [
            "詳細設計のレビュー",
            "テスト方針の策定"
        ],
        "next_date": "2026年07月29日（水）"
    }

    output_bytes = build_minutes_docx(sample_data)
    output_path = "sample_minutes.docx"
    with open(output_path, "wb") as f:
        f.write(output_bytes)
    print(f"Word ファイルを生成しました: {output_path} ({len(output_bytes):,} bytes)")
