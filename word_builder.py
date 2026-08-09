"""
ひな型.docx を編集して議事録Wordを生成する。
AIには触らせず、このモジュールだけが様式を制御する。

実ひな型の構造:
- table[0]: 記録 | 会議名
- table[1]:
  row0 開催日時 / row1 場所 / row2-4 出席者 / row5 資料 /
  row6 議事次第 / row7 議事内容ヘッダー / row8 議事内容本文
本文は table[1]/row8 の結合セルのみに書き込む。
ヘッダー部（日時・場所・出席者・資料・次第）は空欄のまま出力する。
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

# ひな型本文セル内の複製元段落インデックス（実装前に確定）
# p02: 議題下の見出し行（●●●●） → 議題見出し・小項目見出し・説明・質問
# p01: 空行
# p03: 箇条書き行（・） → 回答行（全角ハイフン）
# p15: 日時行 → 次回打合せ
# p17: 以上
PROTO = {
    "topic": 2,
    "blank": 1,
    "subtopic": 2,
    "body": 2,
    "answer": 3,
    "next": 15,
    "end": 17,
}

_CONFIRM_RE = re.compile(r"(\[要確認[^\]]*\])")


def _qname(tag: str) -> str:
    return f"{W}{tag}"


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _clear_cell_keep_one_empty(cell: etree._Element, prototype_p: etree._Element | None = None) -> None:
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


def _set_paragraph_text(p: etree._Element, text: str, highlight_confirm: bool = False) -> None:
    """
    段落のテキストを差し替える。
    既存の最初の run の rPr を流用し、校正マーク等は持ち込まない。
    """
    # 既存 rPr を確保
    first_r = p.find("w:r", NSMAP)
    base_rpr = None
    if first_r is not None:
        rpr = first_r.find("w:rPr", NSMAP)
        if rpr is not None:
            base_rpr = deepcopy(rpr)

    # p 直下の run / proofErr / bookmark 等のうち、テキスト関連を掃除
    for child in list(p):
        local = _local(child.tag)
        if local in ("r", "proofErr", "bookmarkStart", "bookmarkEnd", "del", "ins", "hyperlink"):
            p.remove(child)

    def add_run(run_text: str, color: str | None = None) -> None:
        r = etree.SubElement(p, _qname("r"))
        if base_rpr is not None:
            rpr = deepcopy(base_rpr)
            r.insert(0, rpr)
        else:
            rpr = etree.SubElement(r, _qname("rPr"))
        if color:
            # 既存 color を除去して付与
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
            add_run(text[pos:m.start()])
        add_run(m.group(1), color="FF0000")
        pos = m.end()
    if pos < len(text):
        add_run(text[pos:])


def _make_para(prototype: etree._Element, text: str, highlight_confirm: bool = True) -> etree._Element:
    p = deepcopy(prototype)
    # 校正・変更履歴を除去
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

    # table[0] 会議名を空に
    t0 = tables[0]
    t0_rows = t0.findall("w:tr", NSMAP)
    if t0_rows:
        cells = t0_rows[0].findall("w:tc", NSMAP)
        if len(cells) >= 2:
            proto = cells[1].find("w:p", NSMAP)
            _clear_cell_keep_one_empty(cells[1], proto)

    t1 = tables[1]
    rows = t1.findall("w:tr", NSMAP)

    # row0 日時値, row1 場所値
    for ri in (0, 1):
        cells = rows[ri].findall("w:tc", NSMAP)
        if len(cells) >= 2:
            _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))

    # row2-4 出席者（組織・氏名を空に。ラベル列は触らない）
    for ri in (2, 3, 4):
        cells = rows[ri].findall("w:tc", NSMAP)
        for ci in range(1, len(cells)):
            _clear_cell_keep_one_empty(cells[ci], cells[ci].find("w:p", NSMAP))

    # row5 資料
    cells = rows[5].findall("w:tc", NSMAP)
    if len(cells) >= 2:
        _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))

    # row6 議事次第（値セルを空に）
    cells = rows[6].findall("w:tc", NSMAP)
    if len(cells) >= 2:
        _clear_cell_keep_one_empty(cells[1], cells[1].find("w:p", NSMAP))


def _build_body_paragraphs(prototypes: dict[str, etree._Element], data: dict) -> list[etree._Element]:
    paras: list[etree._Element] = []

    topics = data.get("議題") or []
    for topic in topics:
        heading = f"{topic.get('番号', '')}{topic.get('見出し', '')}"
        paras.append(_make_para(prototypes["topic"], heading))
        paras.append(_make_para(prototypes["blank"], ""))

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
                    # 文末が。でなければ付与はしない（AI側ルールに委ねる）
                    paras.append(_make_para(prototypes["body"], q))
                if a:
                    if not a.startswith("－") and not a.startswith("-"):
                        a = "－" + a
                    paras.append(_make_para(prototypes["answer"], a))

            paras.append(_make_para(prototypes["blank"], ""))

    next_meeting = (data.get("次回打合せ") or "[要確認]").strip()
    paras.append(_make_para(prototypes["next"], f"次回打合せ：{next_meeting}"))
    paras.append(_make_para(prototypes["end"], "以上"))
    paras.append(_make_para(prototypes["blank"], ""))
    return paras


def build_minutes_docx(data: dict, template_path: Path | str | None = None) -> bytes:
    """
    ひな型を編集した議事録docxのバイト列を返す。
    """
    path = Path(template_path) if template_path else TEMPLATE_PATH
    if not path.exists():
        raise FileNotFoundError(f"ひな型が見つかりません: {path}")

    with zipfile.ZipFile(path) as zf:
        original_files = {name: zf.read(name) for name in zf.namelist()}

    root = etree.fromstring(original_files["word/document.xml"])
    tables = root.findall(".//w:tbl", NSMAP)
    body_row = tables[1].findall("w:tr", NSMAP)[8]
    body_cell = body_row.findall("w:tc", NSMAP)[0]

    existing_paras = body_cell.findall("w:p", NSMAP)
    if len(existing_paras) <= max(PROTO.values()):
        raise RuntimeError("ひな型本文の段落数が不足しています。")

    prototypes = {key: existing_paras[idx] for key, idx in PROTO.items()}

    _clear_header_placeholders(root)

    # 本文段落を置換（tcPr は残す）
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
    # pretty print しない（Wordが壊れることがある）

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
        "次回打合せ": "令和８年９月１１日（水）１４時００分～",
    }
    out = build_minutes_docx(sample)
    out_path = Path(__file__).parent / "sample_minutes.docx"
    out_path.write_bytes(out)
    print(f"生成完了: {out_path} ({len(out)} bytes)")
