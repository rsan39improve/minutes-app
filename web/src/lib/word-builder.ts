/**
 * ひな型.docx を編集して議事録Wordを生成する。
 */
import fs from "fs";
import path from "path";
import JSZip from "jszip";
import {
  DOMParser,
  XMLSerializer,
  Element,
  Node,
} from "@xmldom/xmldom";
import type { MinutesData } from "./types";

const W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

const TEMPLATE_PATH = path.join(process.cwd(), "assets", "議事録ひな型.docx");

const PROTO = {
  topic: 0,
  subtopic: 1,
  body: 2,
  blank: 3,
  question: 6,
  answer: 7,
  next: 45,
  end: 48,
} as const;

const CONFIRM_RE = /(\[要確認[^\]]*\])/g;

function local(tag: string): string {
  const brace = tag.indexOf("}");
  if (brace >= 0) return tag.slice(brace + 1);
  const colon = tag.indexOf(":");
  if (colon >= 0) return tag.slice(colon + 1);
  return tag;
}

function qname(tag: string): string {
  return `w:${tag}`;
}

function findChildren(parent: Element, localName: string): Element[] {
  const out: Element[] = [];
  for (let i = 0; i < parent.childNodes.length; i++) {
    const c = parent.childNodes[i];
    if (c.nodeType === 1 && local((c as Element).tagName) === localName) {
      out.push(c as Element);
    }
  }
  return out;
}

function findChild(parent: Element, localName: string): Element | null {
  return findChildren(parent, localName)[0] || null;
}

function findDescendants(root: Element, localName: string): Element[] {
  const out: Element[] = [];
  const walk = (node: Node) => {
    if (node.nodeType === 1) {
      const el = node as Element;
      if (local(el.tagName) === localName) out.push(el);
      for (let i = 0; i < el.childNodes.length; i++) {
        walk(el.childNodes[i]!);
      }
    }
  };
  walk(root);
  return out;
}

function removeChild(parent: Node, child: Node): void {
  parent.removeChild(child);
}

function clearCellKeepOneEmpty(cell: Element, prototypeP: Element | null): void {
  for (const p of findChildren(cell, "p")) {
    removeChild(cell, p);
  }
  if (prototypeP) {
    const p = prototypeP.cloneNode(true) as Element;
    setParagraphText(p, "");
    cell.appendChild(p);
  } else {
    const doc = cell.ownerDocument!;
    cell.appendChild(doc.createElementNS(W_NS, qname("p")));
  }
}

function setParagraphText(
  p: Element,
  text: string,
  highlightConfirm = false,
): void {
  const doc = p.ownerDocument!;
  const firstR = findChild(p, "r");
  let baseRpr: Element | null = null;
  if (firstR) {
    const rpr = findChild(firstR, "rPr");
    if (rpr) baseRpr = rpr.cloneNode(true) as Element;
  }

  const toRemove: Element[] = [];
  for (let i = 0; i < p.childNodes.length; i++) {
    const c = p.childNodes[i];
    if (c.nodeType !== 1) continue;
    const name = local((c as Element).tagName);
    if (
      ["r", "proofErr", "bookmarkStart", "bookmarkEnd", "del", "ins", "hyperlink"].includes(
        name,
      )
    ) {
      toRemove.push(c as Element);
    }
  }
  toRemove.forEach((el) => removeChild(p, el));

  const addRun = (runText: string, color?: string) => {
    const r = doc.createElementNS(W_NS, qname("r"));
    let rpr: Element;
    if (baseRpr) {
      rpr = baseRpr.cloneNode(true) as Element;
      r.appendChild(rpr);
    } else {
      rpr = doc.createElementNS(W_NS, qname("rPr"));
      r.appendChild(rpr);
    }
    if (color) {
      for (const old of findChildren(rpr, "color")) removeChild(rpr, old);
      const colorEl = doc.createElementNS(W_NS, qname("color"));
      colorEl.setAttribute("w:val", color);
      rpr.appendChild(colorEl);
    }
    const t = doc.createElementNS(W_NS, qname("t"));
    if (runText.startsWith(" ") || runText.endsWith(" ") || runText.includes("  ")) {
      t.setAttribute("xml:space", "preserve");
    }
    t.textContent = runText;
    r.appendChild(t);
    p.appendChild(r);
  };

  if (!highlightConfirm || !text.includes("[要確認")) {
    addRun(text);
    return;
  }

  let pos = 0;
  for (const m of text.matchAll(CONFIRM_RE)) {
    const start = m.index ?? 0;
    if (start > pos) addRun(text.slice(pos, start));
    addRun(m[1], "FF0000");
    pos = start + m[0].length;
  }
  if (pos < text.length) addRun(text.slice(pos));
}

function makePara(
  prototype: Element,
  text: string,
  highlightConfirm = true,
): Element {
  const p = prototype.cloneNode(true) as Element;
  const bad = findDescendants(p, "proofErr");
  bad.forEach((el) => el.parentNode && removeChild(el.parentNode, el));
  for (const tag of ["ins", "del"]) {
    const nodes = findDescendants(p, tag);
    nodes.forEach((el) => el.parentNode && removeChild(el.parentNode, el));
  }
  setParagraphText(p, text, highlightConfirm);
  return p;
}

function clearHeaderPlaceholders(root: Element): void {
  const tables = findDescendants(root, "tbl");
  if (tables.length < 2) throw new Error("ひな型に必要なテーブルがありません。");

  const t0Rows = findChildren(tables[0], "tr");
  if (t0Rows[0]) {
    const cells = findChildren(t0Rows[0], "tc");
    if (cells[1]) clearCellKeepOneEmpty(cells[1], findChild(cells[1], "p"));
  }

  const rows = findChildren(tables[1], "tr");
  if (rows.length < 7) {
    throw new Error(
      `ひな型の行数が不足しています（期待:7行以上, 実際:${rows.length}行）。`,
    );
  }

  for (const ri of [0, 1]) {
    const cells = findChildren(rows[ri], "tc");
    if (cells[1]) clearCellKeepOneEmpty(cells[1], findChild(cells[1], "p"));
  }

  for (const ri of [2, 3]) {
    const cells = findChildren(rows[ri], "tc");
    for (const ci of [2, 3]) {
      if (cells[ci]) clearCellKeepOneEmpty(cells[ci], findChild(cells[ci], "p"));
    }
  }

  const cells4 = findChildren(rows[4], "tc");
  if (cells4[1]) clearCellKeepOneEmpty(cells4[1], findChild(cells4[1], "p"));
}

function buildBodyParagraphs(
  prototypes: Record<keyof typeof PROTO, Element>,
  data: MinutesData,
): Element[] {
  const paras: Element[] = [];

  for (const topic of data.議題 || []) {
    paras.push(makePara(prototypes.topic, `${topic.番号 || ""}${topic.見出し || ""}`));
    for (const sub of topic.小項目 || []) {
      paras.push(
        makePara(prototypes.subtopic, `${sub.番号 || ""}${sub.見出し || ""}`),
      );
      const explanation = (sub.説明 || "").trim();
      if (explanation) paras.push(makePara(prototypes.body, explanation));
      for (const qa of sub.質疑 || []) {
        const q = (qa.質問 || "").trim();
        let a = (qa.回答 || "").trim();
        if (q) paras.push(makePara(prototypes.question, q));
        if (a) {
          if (!a.startsWith("－") && !a.startsWith("-")) a = "－" + a;
          paras.push(makePara(prototypes.answer, a));
        }
      }
      paras.push(makePara(prototypes.blank, ""));
    }
  }

  const nextMeeting = (data.次回打合せ || "[要確認]").trim();
  const nextText = nextMeeting.startsWith("次回打合せ")
    ? nextMeeting
    : `次回打合せ：${nextMeeting}`;
  paras.push(makePara(prototypes.next, nextText));
  paras.push(makePara(prototypes.blank, ""));
  paras.push(makePara(prototypes.end, "以上"));
  return paras;
}

function enableBodyTablePageFlow(table: Element): void {
  const tblPr = findChild(table, "tblPr");
  if (tblPr) {
    for (const el of findChildren(tblPr, "tblpPr")) removeChild(tblPr, el);
  }
  const rows = findChildren(table, "tr");
  const bodyRow = rows[rows.length - 1];
  if (!bodyRow) return;
  const trPr = findChild(bodyRow, "trPr");
  if (!trPr) return;
  for (const el of findChildren(trPr, "trHeight")) removeChild(trPr, el);
  for (const el of findChildren(trPr, "cantSplit")) removeChild(trPr, el);
}

function ensureGapBetweenTitleAndBody(root: Element): void {
  const body = findChild(root, "body");
  if (!body) return;
  const directTables = findChildren(body, "tbl");
  if (directTables.length < 2) return;
  const [titleTbl, bodyTbl] = directTables;

  let sibling = titleTbl.nextSibling;
  while (sibling && sibling !== bodyTbl) {
    if (sibling.nodeType === 1 && local((sibling as Element).tagName) === "p") {
      return;
    }
    sibling = sibling.nextSibling;
  }

  const doc = root.ownerDocument!;
  const gap = doc.createElementNS(W_NS, qname("p"));
  const pPr = doc.createElementNS(W_NS, qname("pPr"));
  const spacing = doc.createElementNS(W_NS, qname("spacing"));
  spacing.setAttribute("w:before", "0");
  spacing.setAttribute("w:after", "0");
  spacing.setAttribute("w:line", "240");
  spacing.setAttribute("w:lineRule", "auto");
  pPr.appendChild(spacing);
  gap.appendChild(pPr);
  body.insertBefore(gap, bodyTbl);
}

export async function buildMinutesDocx(
  data: MinutesData,
  templatePath = TEMPLATE_PATH,
): Promise<Buffer> {
  if (!fs.existsSync(templatePath)) {
    throw new Error(`ひな型が見つかりません: ${templatePath}`);
  }

  const zip = await JSZip.loadAsync(fs.readFileSync(templatePath));
  const xmlFile = zip.file("word/document.xml");
  if (!xmlFile) throw new Error("word/document.xml がありません。");
  const xmlText = await xmlFile.async("text");

  const dom = new DOMParser().parseFromString(xmlText, "text/xml");
  const root = dom.documentElement;
  if (!root) throw new Error("document.xml のルート要素がありません。");
  const tables = findDescendants(root, "tbl");
  if (tables.length < 2) throw new Error("ひな型に必要なテーブルがありません。");
  enableBodyTablePageFlow(tables[1]);
  ensureGapBetweenTitleAndBody(root);

  const bodyRow = findChildren(tables[1], "tr")[6];
  if (!bodyRow) throw new Error("ひな型の本文行（row6）が見つかりません。");
  const bodyCells = findChildren(bodyRow, "tc");
  if (bodyCells.length < 2) {
    throw new Error("ひな型の議事内容行にセルが不足しています。");
  }
  const bodyCell = bodyCells[1];
  const existingParas = findChildren(bodyCell, "p");
  const maxProto = Math.max(...Object.values(PROTO));
  if (existingParas.length <= maxProto) {
    throw new Error(
      `ひな型本文の段落数が不足しています（${existingParas.length}段落）。`,
    );
  }

  const prototypes = {
    topic: existingParas[PROTO.topic],
    subtopic: existingParas[PROTO.subtopic],
    body: existingParas[PROTO.body],
    blank: existingParas[PROTO.blank],
    question: existingParas[PROTO.question],
    answer: existingParas[PROTO.answer],
    next: existingParas[PROTO.next],
    end: existingParas[PROTO.end],
  };

  clearHeaderPlaceholders(root);
  for (const p of findChildren(bodyCell, "p")) removeChild(bodyCell, p);
  for (const p of buildBodyParagraphs(prototypes, data)) bodyCell.appendChild(p);

  const newXml = new XMLSerializer().serializeToString(dom);
  const declaration = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const outXml = newXml.startsWith("<?xml") ? newXml : declaration + newXml;

  zip.file("word/document.xml", outXml);
  const out = await zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
  });
  return Buffer.from(out);
}
