import { NextResponse } from "next/server";
import { isAuthenticated } from "@/lib/auth";
import { extractTextFromUpload, normalizeTranscript } from "@/lib/extractor";
import { extractMinutes } from "@/lib/llm";
import { applyNumberCheck, collectConfirmationTags } from "@/lib/number-check";
import { buildMinutesDocx } from "@/lib/word-builder";
import {
  MAX_TOTAL_UPLOAD_BYTES,
  MAX_TOTAL_UPLOAD_LABEL,
} from "@/lib/upload-limits";

export const maxDuration = 120;

async function readFieldText(
  form: FormData,
  textKey: string,
  fileKey: string,
): Promise<{ text: string; warnings: string[] }> {
  const warnings: string[] = [];
  const pasted = String(form.get(textKey) || "").trim();
  if (pasted) return { text: pasted, warnings };

  const file = form.get(fileKey);
  if (file && typeof file !== "string" && file.size > 0) {
    const buf = Buffer.from(await file.arrayBuffer());
    const { text, warning } = await extractTextFromUpload(buf, file.name);
    if (warning) warnings.push(warning);
    return { text: text || "", warnings };
  }
  return { text: "", warnings };
}

export async function POST(request: Request) {
  if (!(await isAuthenticated())) {
    return NextResponse.json({ error: "認証が必要です。" }, { status: 401 });
  }
  if (!process.env.ANTHROPIC_API_KEY) {
    return NextResponse.json(
      { error: "管理者設定（APIキー）が未完了のため、現在使用できません。" },
      { status: 503 },
    );
  }

  try {
    const form = await request.formData();
    const totalUploadBytes = [
      "transcriptFile",
      "agendaFile",
      "materialsFile",
    ].reduce((total, key) => {
      const file = form.get(key);
      return total + (file && typeof file !== "string" ? file.size : 0);
    }, 0);
    if (totalUploadBytes > MAX_TOTAL_UPLOAD_BYTES) {
      return NextResponse.json(
        {
          error: `ファイルの合計容量を${MAX_TOTAL_UPLOAD_LABEL}以下にしてください。`,
        },
        { status: 413 },
      );
    }

    const transcriptPart = await readFieldText(
      form,
      "transcriptText",
      "transcriptFile",
    );
    const agendaPart = await readFieldText(form, "agendaText", "agendaFile");
    const materialsPart = await readFieldText(form, "materialsText", "materialsFile");

    const warnings = [
      ...transcriptPart.warnings,
      ...agendaPart.warnings,
      ...materialsPart.warnings,
    ];

    if (!transcriptPart.text) {
      return NextResponse.json(
        { error: "発言ログ（文字起こし）は必須です。", warnings },
        { status: 400 },
      );
    }

    const transcript = normalizeTranscript(transcriptPart.text);
    let minutes = await extractMinutes(
      transcript,
      materialsPart.text,
      agendaPart.text,
    );
    minutes = applyNumberCheck(minutes, transcript);
    const confirms = collectConfirmationTags(minutes);
    const docx = await buildMinutesDocx(minutes);
    const filename = `議事録_${new Date()
      .toISOString()
      .slice(0, 10)
      .replace(/-/g, "")}.docx`;

    return NextResponse.json({
      minutes,
      confirms,
      warnings,
      filename,
      docxBase64: docx.toString("base64"),
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
