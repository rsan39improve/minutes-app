"""
ひな型.docx を編集して議事録Wordを生成する。
AIには触らせず、このモジュールだけが様式を制御する。

ひな型構造（2026-08更新）:
- table[0]: 記録 | 会議名
- table[1]:
  row0 開催日時 / row1 場所 / row2-3 出席者(委託者・受注者) /
  row4 資料 / row5 発言者|議事内容ヘッダー /
  row6 cell0 発言者列（市・UD等） / cell1 議事内容本文
本文は table[1]/row6/cell1 のみに書き込む。
発言者列（cell0）は触らない。
ヘッダー部（日時・場所・出席者名・資料・会議名）は空欄のまま出力する。
"""

from __future__ import annotations

import io
import re
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree

NSMAP = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

TEMPLATE_PATH = Path(__file__).parent / "議事録ひな型.docx"

# 本文セル（row6/cell1）内の複製元段落インデックス
# p0: 議題見出し「１．…」
# p1: 小項目見出し「（１）…」
# p2: 説明文
# p3: 空行（前後の段落から取得）
# p6: 質問行
# p7: 回答行「－…」
# p45: 次回打合せ：
# p48: 以上
PROTO = {
    "topic": 0,
    "subtopic": 1,
    "body": 2,
    "blank": 3,
    "question": 6,
    "answer": 7,
    "next": 45,
    "end": 48,
}

_CONFIRM_RE = re.compile(r"(\[要確認[^\]]*\])")


def _qname(tag: str) -> str:
    return f"{W}{tag}"


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _clear_cell_keep_one_empty(
    cell: etree._Element, prototype_p: etree._Element | None = None
) -> None:
    """セル内段落をすべて消し、空の段落を1つ残す。"""
    for child in list(cell):
        if _local(child.tag) == "p":
            cell.remove(child)
    if prototype_p is not None:
        p = deepcopy(prototype_p)
        _set_paragraph_text(p, "")
        cell.append(p)
    else:
        cell.append(etree.Element(_qname("p")))


def _set_paragraph_text(
    p: etree._Element, text: str, highlight_confirm: bool = False
) -> None:
    """段落テキストを差し替える。既存 run の rPr を流用する。"""
    first_r = p.find("w:r", NSMAP)
    base_rpr = None
    if first_r is not None:
        rpr = first_r.find("w:rPr", NSMAP)
        if rpr is not None:
            base_rpr = deepcopy(rpr)

    for child in list(p):
        local = _local(child.tag)
        if local in (
            "r",
            "proofErr",
            "bookmarkStart",
            "bookmarkEnd",
            "del",
            "ins",
            "hyperlink",
        ):
            p.remove(child)

    def add_run(run_text: str, color: str | None = None) -> None:
        r = etree.SubElement(p, _qname("r"))
        if base_rpr is not None:
            rpr = deepcopy(base_rpr)
            r.insert(0, rpr)
        else:
            rpr = etree.SubElement(r, _qname("rPr"))
        if color:
            for old in rpr.findall("w:color", NSMAP):
                rpr.remove(old)
            color_el = etree.SubElement(rpr, _qname("color"))
            color_el.set(_qname("val"), color)
        t = etree.SubElement(r, _qname("t"))
        if run_text.startswith(" ") or run_text.endswith(" ") or "  " in run_text:
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = run_text

    if not highlight_confirm or "[要確認" not in text:
        add_run(text)
        return

    pos = 0
    for m in _CONFIRM_RE.finditer(text):
        if m.start() > pos:
            add_run(text[pos : m.start()])
        add_run(m.group(1), color="FF0000")
        pos = m.end()
    if pos < len(text):
        add_run(text[pos:])


def _make_para(
    prototype: etree._Element, text: str, highlight_confirm: bool = True
) -> etree._Element:
    p = deepcopy(prototype)
    for bad in p.findall(".//w:proofErr", NSMAP):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)
    for bad_tag in ("ins", "del"):
        for bad in p.findall(f".//w:{bad_tag}", NSMAP):
            parent = bad.getparent()
            if parent is not None:
                parent.remove(bad)
    _set_paragraph_text(p, text, highlight_confirm=highlight_confirm)
    return p


def _clear_header_placeholders(root: etree._Element) -> None:
    tables = root.findall(".//w:tbl", NSMAP)
    if len(tables) < 2:
        raise RuntimeError("ひな型に必要なテーブルがありません。")

    # table[0] 会議名を空に（「記録」は残す）
    t0_rows = tables[0].findall("w:tr", NSMAP)
    if t0_rows:
        cells = t0_rows[0].findall("w:tc", NSMAP)
        if len(cells) >= 2:
            _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))

    rows = tables[1].findall("w:tr", NSMAP)
    if len(rows) < 7:
        raise RuntimeError(
            f"ひな型の行数が不足しています（期待:7行以上, 実際:{len(rows)}行）。"
        )

    # row0 日時 / row1 場所
    for ri in (0, 1):
        cells = rows[ri].findall("w:tc", NSMAP)
        if len(cells) >= 2:
            _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))

    # row2-3 出席者: 「委託者」「受注者」ラベルは残し、組織名・氏名を空に
    for ri in (2, 3):
        cells = rows[ri].findall("w:tc", NSMAP)
        for ci in (2, 3):
            if ci < len(cells):
                _clear_cell_keep_one_empty(cells[ci], cells[ci].find("w:p", NSMAP))

    # row4 資料
    cells = rows[4].findall("w:tc", NSMAP)
    if len(cells) >= 2:
        _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))


def _build_body_paragraphs(
    prototypes: dict[str, etree._Element], data: dict
) -> list[etree._Element]:
    paras: list[etree._Element] = []

    for topic in data.get("議題") or []:
        heading = f"{topic.get('番号', '')}{topic.get('見出し', '')}"
        paras.append(_make_para(prototypes["topic"], heading))

        for sub in topic.get("小項目") or []:
            sub_heading = f"{sub.get('番号', '')}{sub.get('見出し', '')}"
            paras.append(_make_para(prototypes["subtopic"], sub_heading))

            explanation = (sub.get("説明") or "").strip()
            if explanation:
                paras.append(_make_para(prototypes["body"], explanation))

            for qa in sub.get("質疑") or []:
                q = (qa.get("質問") or "").strip()
                a = (qa.get("回答") or "").strip()
                if q:
                    paras.append(_make_para(prototypes["question"], q))
                if a:
                    if not a.startswith("－") and not a.startswith("-"):
                        a = "－" + a
                    paras.append(_make_para(prototypes["answer"], a))

            paras.append(_make_para(prototypes["blank"], ""))

    next_meeting = (data.get("次回打合せ") or "[要確認]").strip()
    # ひな型は「次回打合せ：」のみの行なので、内容を続けて書く
    if next_meeting.startswith("次回打合せ"):
        next_text = next_meeting
    else:
        next_text = f"次回打合せ：{next_meeting}"
    paras.append(_make_para(prototypes["next"], next_text))
    paras.append(_make_para(prototypes["blank"], ""))
    paras.append(_make_para(prototypes["end"], "以上"))
    return paras


def _enable_body_table_page_flow(table: etree._Element) -> None:
    """
    本文テーブルがページをまたげるようにする。

    ひな型の table[1] には tblpPr（浮き表）が付いており、
    Wordでは浮き表の行がページをまたげず、長い議事内容の後半が
    見えない／切れることがある。インライン表に戻して解消する。
    """
    tbl_pr = table.find("w:tblPr", NSMAP)
    if tbl_pr is not None:
        for el in tbl_pr.findall("w:tblpPr", NSMAP):
            tbl_pr.remove(el)

    # 本文行（最終行）の固定高さ・分割禁止があれば外す
    rows = table.findall("w:tr", NSMAP)
    if not rows:
        return
    body_row = rows[-1]
    tr_pr = body_row.find("w:trPr", NSMAP)
    if tr_pr is None:
        return
    for el in tr_pr.findall("w:trHeight", NSMAP):
        tr_pr.remove(el)
    for el in tr_pr.findall("w:cantSplit", NSMAP):
        tr_pr.remove(el)


def _ensure_gap_between_title_and_body(root: etree._Element) -> None:
    """
    「記録」タイトル表と本文表のあいだに1行分の空きを入れる。

    ひな型では本文表の浮き位置(tblpY)で隙間が出ていたが、
    ページ送りのために浮き設定を外すと隙間も消えるため、空段落で補う。
    """
    body = root.find("w:body", NSMAP)
    if body is None:
        return
    direct_tables = [c for c in list(body) if _local(c.tag) == "tbl"]
    if len(direct_tables) < 2:
        return
    title_tbl, body_tbl = direct_tables[0], direct_tables[1]

    # すでに間に段落があれば何もしない
    sibling = title_tbl.getnext()
    while sibling is not None and sibling is not body_tbl:
        if _local(sibling.tag) == "p":
            return
        sibling = sibling.getnext()

    gap = etree.Element(_qname("p"))
    p_pr = etree.SubElement(gap, _qname("pPr"))
    spacing = etree.SubElement(p_pr, _qname("spacing"))
    spacing.set(_qname("before"), "0")
    spacing.set(_qname("after"), "0")
    spacing.set(_qname("line"), "240")  # 1行
    spacing.set(_qname("lineRule"), "auto")
    body_tbl.addprevious(gap)


def build_minutes_docx(data: dict, template_path: Path | str | None = None) -> bytes:
    """ひな型を編集した議事録docxのバイト列を返す。"""
    path = Path(template_path) if template_path else TEMPLATE_PATH
    if not path.exists():
        raise FileNotFoundError(f"ひな型が見つかりません: {path}")

    with zipfile.ZipFile(path) as zf:
        original_files = {name: zf.read(name) for name in zf.namelist()}

    root = etree.fromstring(original_files["word/document.xml"])
    tables = root.findall(".//w:tbl", NSMAP)
    _enable_body_table_page_flow(tables[1])
    _ensure_gap_between_title_and_body(root)

    body_row = tables[1].findall("w:tr", NSMAP)[6]
    body_cells = body_row.findall("w:tc", NSMAP)
    if len(body_cells) < 2:
        raise RuntimeError("ひな型の議事内容行にセルが不足しています。")

    # cell0=発言者列（触らない）, cell1=議事内容
    body_cell = body_cells[1]
    existing_paras = body_cell.findall("w:p", NSMAP)
    if len(existing_paras) <= max(PROTO.values()):
        raise RuntimeError(
            f"ひな型本文の段落数が不足しています（{len(existing_paras)}段落）。"
        )

    prototypes = {key: existing_paras[idx] for key, idx in PROTO.items()}

    _clear_header_placeholders(root)

    for p in body_cell.findall("w:p", NSMAP):
        body_cell.remove(p)
    for p in _build_body_paragraphs(prototypes, data):
        body_cell.append(p)

    new_xml = etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, content in original_files.items():
            if name == "word/document.xml":
                out.writestr(name, new_xml)
            else:
                out.writestr(name, content)
    return buf.getvalue()


if __name__ == "__main__":
    sample = {
        "議題": [
            {
                "番号": "１．",
                "見出し": "契約書および業務着手時提出書類等の確認",
                "小項目": [
                    {
                        "番号": "（１）",
                        "見出し": "契約書",
                        "説明": "委託者より契約書を受領した。",
                        "質疑": [
                            {
                                "質問": "提出期限はいつか。",
                                "回答": "来週金曜までとする。",
                                "話者": "A",
                            }
                        ],
                    }
                ],
            }
        ],
        "次回打合せ": "[要確認]",
    }
    out = build_minutes_docx(sample)
    out_path = Path(__file__).parent / "sample_minutes.docx"
    out_path.write_bytes(out)
    print(f"生成完了: {out_path} ({len(out)} bytes)")
