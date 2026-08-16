import Anthropic from "@anthropic-ai/sdk";
import fs from "fs";
import path from "path";
import type { MinutesData } from "./types";

const SYSTEM_PROMPT_PATH = path.join(process.cwd(), "prompts", "minutes.txt");

function loadSystemPrompt(): string {
  if (!fs.existsSync(SYSTEM_PROMPT_PATH)) {
    throw new Error(`システムプロンプトが見つかりません: ${SYSTEM_PROMPT_PATH}`);
  }
  return fs.readFileSync(SYSTEM_PROMPT_PATH, "utf-8").trim();
}

const MINUTES_TOOL: Anthropic.Tool = {
  name: "extract_minutes",
  description:
    "発言ログから議事録本文の構造データを抽出する（ヘッダー情報は含まない）",
  input_schema: {
    type: "object",
    properties: {
      topics: {
        type: "array",
        description: "議題ごとの構成",
        items: {
          type: "object",
          properties: {
            number: { type: "string", description: "全角番号。例: １．" },
            title: { type: "string", description: "議題見出し" },
            subtopics: {
              type: "array",
              description: "小項目の配列",
              items: {
                type: "object",
                properties: {
                  number: { type: "string", description: "全角番号。例: （１）" },
                  title: { type: "string", description: "小項目見出し" },
                  description: {
                    type: "string",
                    description: "確認・報告された事実（1〜2文、常体）",
                  },
                  qa: {
                    type: "array",
                    description: "質疑の配列",
                    items: {
                      type: "object",
                      properties: {
                        question: { type: "string", description: "質問文" },
                        answer: { type: "string", description: "回答文" },
                        speaker: {
                          type: "string",
                          description: "発言ログの話者ラベル（A、B等）",
                        },
                      },
                      required: ["question", "answer", "speaker"],
                    },
                  },
                },
                required: ["number", "title", "description", "qa"],
              },
            },
          },
          required: ["number", "title", "subtopics"],
        },
      },
      next_meeting: {
        type: "string",
        description: "次回打合せ日時等。読み取れない場合は [要確認]",
      },
    },
    required: ["topics", "next_meeting"],
  },
};

type RawMinutes = {
  topics?: Array<{
    number?: string;
    title?: string;
    subtopics?: Array<{
      number?: string;
      title?: string;
      description?: string;
      qa?: Array<{ question?: string; answer?: string; speaker?: string }>;
    }>;
  }>;
  next_meeting?: string;
};

function toAppFormat(raw: RawMinutes): MinutesData {
  const topics = (raw.topics || []).map((topic) => ({
    番号: topic.number || "",
    見出し: topic.title || "",
    小項目: (topic.subtopics || []).map((sub) => ({
      番号: sub.number || "",
      見出し: sub.title || "",
      説明: sub.description || "",
      質疑: (sub.qa || []).map((qa) => ({
        質問: qa.question || "",
        回答: qa.answer || "",
        話者: qa.speaker || "",
      })),
    })),
  }));
  return {
    議題: topics,
    次回打合せ: raw.next_meeting || "[要確認]",
  };
}

export async function extractMinutes(
  transcript: string,
  materials = "",
  agenda = "",
): Promise<MinutesData> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error(
      "ANTHROPIC_API_KEY が設定されていません。.env.local を確認してください。",
    );
  }

  const client = new Anthropic({ apiKey });
  const systemPrompt = loadSystemPrompt();
  const userContent =
    `【発言ログ】\n${transcript.trim()}\n\n` +
    `【打合せ次第】\n${(agenda || "").trim() || "（なし）"}\n\n` +
    `【その他資料】\n${(materials || "").trim() || "（なし）"}\n\n` +
    "上記から議事録JSONを生成してください。";

  const response = await client.messages.create({
    model: "claude-sonnet-4-5",
    max_tokens: 8000,
    system: systemPrompt,
    tools: [MINUTES_TOOL],
    tool_choice: { type: "tool", name: "extract_minutes" },
    messages: [{ role: "user", content: userContent }],
  });

  for (const block of response.content) {
    if (block.type === "tool_use" && block.name === "extract_minutes") {
      return toAppFormat(block.input as RawMinutes);
    }
  }
  throw new Error("AIから議事録データを取得できませんでした。");
}
