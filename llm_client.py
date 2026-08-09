"""
LLM呼び出しモジュール。
Anthropic Structured Outputs (tool_use) でJSON Schemaを強制し、出力のブレを排除する。
AIは議事本文（議題・小項目・質疑・次回打合せ）のみを返す。
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
            "議題": {
                "type": "array",
                "description": "議題ごとの構成",
                "items": {
                    "type": "object",
                    "properties": {
                        "番号": {
                            "type": "string",
                            "description": "全角番号。例: １．",
                        },
                        "見出し": {
                            "type": "string",
                            "description": "議題見出し",
                        },
                        "小項目": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "番号": {
                                        "type": "string",
                                        "description": "全角番号。例: （１）",
                                    },
                                    "見出し": {
                                        "type": "string",
                                        "description": "小項目見出し",
                                    },
                                    "説明": {
                                        "type": "string",
                                        "description": "確認・報告された事実（1〜2文、常体）",
                                    },
                                    "質疑": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "質問": {"type": "string"},
                                                "回答": {"type": "string"},
                                                "話者": {
                                                    "type": "string",
                                                    "description": "発言ログの話者ラベル（A、B等）",
                                                },
                                            },
                                            "required": ["質問", "回答", "話者"],
                                        },
                                    },
                                },
                                "required": ["番号", "見出し", "説明", "質疑"],
                            },
                        },
                    },
                    "required": ["番号", "見出し", "小項目"],
                },
            },
            "次回打合せ": {
                "type": "string",
                "description": "次回打合せ日時等。読み取れない場合は [要確認]",
            },
        },
        "required": ["議題", "次回打合せ"],
    },
}


def extract_minutes(
    transcript: str,
    materials: str = "",
    agenda: str = "",
) -> dict:
    """
    発言ログ・当日資料・打合せ次第から議事録本文JSONを抽出する。
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
        f"【当日資料】\n{(materials or '').strip() or '（なし）'}\n\n"
        f"【打合せ次第】\n{(agenda or '').strip() or '（なし）'}\n\n"
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
            return block.input

    raise RuntimeError("LLMからの構造化データ取得に失敗しました。")


if __name__ == "__main__":
    sample_transcript = """
A: 本日は権利者ヒアリングについてです。現時点で15社以上にヒアリング済みです。
B: 次回は令和８年９月１１日（水）１４時００分からでお願いします。
A: 承知しました。
"""
    result = extract_minutes(sample_transcript, agenda="１．権利者ヒアリング")
    print(json.dumps(result, ensure_ascii=False, indent=2))
