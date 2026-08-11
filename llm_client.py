"""
LLM呼び出しモジュール。
Anthropic Structured Outputs (tool_use) でJSON Schemaを強制し、出力のブレを排除する。
AIは議事本文（議題・小項目・質疑・次回打合せ）のみを返す。

注: Anthropic API の tool input_schema のプロパティ名は
ASCII（^[a-zA-Z0-9_.-]{1,64}$）のみ許可されるため、スキーマは英語キー。
アプリ内では日本語キーへ変換してから返す。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "minutes.txt"


def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"システムプロンプトが見つかりません: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()


MINUTES_SCHEMA = {
    "name": "extract_minutes",
    "description": "発言ログから議事録本文の構造データを抽出する（ヘッダー情報は含まない）",
    "input_schema": {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "description": "議題ごとの構成",
                "items": {
                    "type": "object",
                    "properties": {
                        "number": {
                            "type": "string",
                            "description": "全角番号。例: １．",
                        },
                        "title": {
                            "type": "string",
                            "description": "議題見出し",
                        },
                        "subtopics": {
                            "type": "array",
                            "description": "小項目の配列",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "number": {
                                        "type": "string",
                                        "description": "全角番号。例: （１）",
                                    },
                                    "title": {
                                        "type": "string",
                                        "description": "小項目見出し",
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "確認・報告された事実（1〜2文、常体）",
                                    },
                                    "qa": {
                                        "type": "array",
                                        "description": "質疑の配列",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "question": {
                                                    "type": "string",
                                                    "description": "質問文",
                                                },
                                                "answer": {
                                                    "type": "string",
                                                    "description": "回答文",
                                                },
                                                "speaker": {
                                                    "type": "string",
                                                    "description": "発言ログの話者ラベル（A、B等）",
                                                },
                                            },
                                            "required": ["question", "answer", "speaker"],
                                        },
                                    },
                                },
                                "required": ["number", "title", "description", "qa"],
                            },
                        },
                    },
                    "required": ["number", "title", "subtopics"],
                },
            },
            "next_meeting": {
                "type": "string",
                "description": "次回打合せ日時等。読み取れない場合は [要確認]",
            },
        },
        "required": ["topics", "next_meeting"],
    },
}


def _to_app_format(raw: dict) -> dict:
    """API英語キー → アプリ内日本語キーへ変換する。"""
    topics = []
    for topic in raw.get("topics") or []:
        subtopics = []
        for sub in topic.get("subtopics") or []:
            qas = []
            for qa in sub.get("qa") or []:
                qas.append(
                    {
                        "質問": qa.get("question", "") or "",
                        "回答": qa.get("answer", "") or "",
                        "話者": qa.get("speaker", "") or "",
                    }
                )
            subtopics.append(
                {
                    "番号": sub.get("number", "") or "",
                    "見出し": sub.get("title", "") or "",
                    "説明": sub.get("description", "") or "",
                    "質疑": qas,
                }
            )
        topics.append(
            {
                "番号": topic.get("number", "") or "",
                "見出し": topic.get("title", "") or "",
                "小項目": subtopics,
            }
        )
    next_meeting = raw.get("next_meeting") or "[要確認]"
    return {"議題": topics, "次回打合せ": next_meeting}


def extract_minutes(
    transcript: str,
    materials: str = "",
    agenda: str = "",
) -> dict:
    """
    発言ログ・当日資料・打合せ次第から議事録本文JSONを抽出する。
    戻り値はアプリ内形式（日本語キー）。
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY が設定されていません。.env または Secrets を確認してください。"
        )

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt = _load_system_prompt()

    user_content = (
        f"【発言ログ】\n{transcript.strip()}\n\n"
        f"【打合せ次第】\n{(agenda or '').strip() or '（なし）'}\n\n"
        f"【その他資料】\n{(materials or '').strip() or '（なし）'}\n\n"
        "上記から議事録JSONを生成してください。"
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8000,
        system=system_prompt,
        tools=[MINUTES_SCHEMA],
        tool_choice={"type": "tool", "name": "extract_minutes"},
        messages=[{"role": "user", "content": user_content}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_minutes":
            return _to_app_format(block.input)

    raise RuntimeError("LLMからの構造化データ取得に失敗しました。")


if __name__ == "__main__":
    sample_transcript = """
A: 本日は権利者ヒアリングについてです。現時点で15社以上にヒアリング済みです。
B: 次回は令和８年９月１１日（水）１４時００分からでお願いします。
A: 承知しました。
"""
    result = extract_minutes(sample_transcript, agenda="１．権利者ヒアリング")
    print(json.dumps(result, ensure_ascii=False, indent=2))
