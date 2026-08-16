import mammoth from "mammoth";

export const MAX_TRANSCRIPT_CHARS = 100_000;

export class EmptyPdfTextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EmptyPdfTextError";
  }
}

async function extractTextFromPdf(file: Buffer): Promise<string> {
  // pdf-parse は画像描画用のネイティブ依存を初期化するため、
  // PDFを扱う時だけ読み込む。txt/docx の処理まで巻き込んで落とさない。
  await import("@napi-rs/canvas");
  const { PDFParse } = await import("pdf-parse");
  const parser = new PDFParse({ data: file });
  try {
    const result = await parser.getText();
    const text = (result.text || "").trim();
    if (!text) {
      throw new EmptyPdfTextError(
        "PDFから文字を抽出できませんでした（スキャン画像の可能性）。",
      );
    }
    return text;
  } finally {
    await parser.destroy?.();
  }
}

function extractTextFromTxt(file: Buffer): string {
  for (const encoding of ["utf-8", "utf-8-sig", "shift_jis"] as const) {
    try {
      const decoder = new TextDecoder(encoding, { fatal: true });
      return decoder.decode(file);
    } catch {
      /* try next */
    }
  }
  return new TextDecoder("utf-8").decode(file);
}

async function extractTextFromDocx(file: Buffer): Promise<string> {
  const result = await mammoth.extractRawText({ buffer: file });
  return (result.value || "").trim();
}

export async function extractTextFromUpload(
  fileBytes: Buffer,
  filename: string,
): Promise<{ text: string | null; warning: string | null }> {
  const name = (filename || "").toLowerCase();
  try {
    if (name.endsWith(".pdf")) {
      return { text: await extractTextFromPdf(fileBytes), warning: null };
    }
    if (name.endsWith(".docx")) {
      const text = await extractTextFromDocx(fileBytes);
      if (!text) {
        return {
          text: null,
          warning: "Wordファイルから文字を抽出できませんでした。",
        };
      }
      return { text, warning: null };
    }
    const text = extractTextFromTxt(fileBytes).trim();
    if (!text) {
      return { text: null, warning: "テキストファイルが空です。" };
    }
    return { text, warning: null };
  } catch (e) {
    if (e instanceof EmptyPdfTextError) {
      return { text: null, warning: e.message };
    }
    return {
      text: null,
      warning: `ファイル読み込みエラー: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

export function normalizeTranscript(text: string): string {
  const cleaned = (text || "").trim();
  if (cleaned.length > MAX_TRANSCRIPT_CHARS) {
    throw new Error(
      `文字起こしが長すぎます（${cleaned.length.toLocaleString()}文字）。上限は ${MAX_TRANSCRIPT_CHARS.toLocaleString()} 文字です。`,
    );
  }
  return cleaned;
}
