import type { MinutesData } from "./types";

const NUM_EXPR =
  /[^\s　、。．，,・\n]{0,12}[0-9０-９][^\s　、。．，,・\n]{0,20}/g;

const TAG = "[要確認：数値未照合]";

function extractNumericExprs(text: string): string[] {
  if (!text) return [];
  const found: string[] = [];
  for (const m of text.matchAll(NUM_EXPR)) {
    const expr = m[0].replace(/^[「」『』（）()[\]【】]+|[「」『』（）()[\]【】]+$/g, "");
    if (expr && !found.includes(expr)) found.push(expr);
  }
  return found;
}

function flagIfNeeded(text: string, transcript: string): string {
  if (!text || text.includes(TAG)) return text;
  for (const expr of extractNumericExprs(text)) {
    if (!transcript.includes(expr)) {
      return text.replace(/\s*$/, "") + TAG;
    }
  }
  return text;
}

export function applyNumberCheck(
  minutesData: MinutesData,
  transcript: string,
): MinutesData {
  const data = structuredClone(minutesData);
  const source = transcript || "";

  for (const topic of data.議題 || []) {
    topic.見出し = flagIfNeeded(topic.見出し || "", source);
    for (const sub of topic.小項目 || []) {
      sub.見出し = flagIfNeeded(sub.見出し || "", source);
      sub.説明 = flagIfNeeded(sub.説明 || "", source);
      for (const qa of sub.質疑 || []) {
        qa.質問 = flagIfNeeded(qa.質問 || "", source);
        qa.回答 = flagIfNeeded(qa.回答 || "", source);
      }
    }
  }
  data.次回打合せ = flagIfNeeded(data.次回打合せ || "", source);
  return data;
}

export function collectConfirmationTags(minutesData: MinutesData): string[] {
  const hits: string[] = [];

  function walk(value: unknown): void {
    if (typeof value === "string") {
      if (value.includes("[要確認")) hits.push(value);
    } else if (Array.isArray(value)) {
      value.forEach(walk);
    } else if (value && typeof value === "object") {
      Object.values(value).forEach(walk);
    }
  }

  walk(minutesData);
  return hits;
}
