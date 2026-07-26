"""
LLM呼び出しモジュール。
Anthropic Structured Outputs (tool_use) でJSON Schemaを強制し、出力のブレを排除する。
"""

import json
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

# 出力JSONの構造定義（ひな型の様式に対応）
MINUTES_SCHEMA = {
    "name": "extract_minutes",
    "description": "会議の文字起こしから議事録の構造データを抽出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "meeting_name": {
                "type": "string",
                "description": "会議名・打合せ名。資料や文字起こしから推定する。不明な場合は「打合せ」とする。"
            },
            "date": {
                "type": "string",
                "description": "開催日時。形式: 令和〇年〇月〇日（〇）〇時〇分～〇時〇分。不明な場合は空文字。"
            },
            "location": {
                "type": "string",
                "description": "開催場所。文字起こしや資料から読み取る。不明な場合は空文字。"
            },
            "participants": {
                "type": "array",
                "description": "出席者リスト。会社・組織ごとに1エントリ作成する。",
                "items": {
                    "type": "object",
                    "properties": {
                        "organization": {
                            "type": "string",
                            "description": "会社名・役職・立場（例：〇〇株式会社（事務局）、事業協力者：△△株式会社）"
                        },
                        "names": {
                            "type": "string",
                            "description": "その会社・組織の出席者名を読点区切りで記載（例：田中、山田）"
                        }
                    },
                    "required": ["organization", "names"]
                }
            },
            "materials": {
                "type": "array",
                "items": {"type": "string"},
                "description": "配布資料名のリスト。「資料〇 〇〇（〇〇作成）」の形式で。言及がなければ空配列。"
            },
            "agenda_summary": {
                "type": "array",
                "items": {"type": "string"},
                "description": "議事次第の箇条書き。「１．〇〇」「２．〇〇」の形式で番号付き。資料のアジェンダから抽出する。"
            },
            "agenda_items": {
                "type": "array",
                "description": "議題ごとの議論内容",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "議題タイトル"
                        },
                        "discussion": {
                            "type": "string",
                            "description": "その議題における議論・説明の要点（200字程度）"
                        }
                    },
                    "required": ["title", "discussion"]
                }
            },
            "decisions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "会議で決定した事項のリスト。「〜することになった」「〜に決定した」などを抽出。「〜とする」の形で記述。"
            },
            "next_topics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "次回の検討事項・宿題のリスト。"
            },
            "next_date": {
                "type": "string",
                "description": "次回開催日時。形式: 令和〇年〇月〇日（〇）〇時〇分～。不明または言及なければ空文字。"
            },
            "next_location": {
                "type": "string",
                "description": "次回開催場所。不明または言及なければ空文字。"
            }
        },
        "required": [
            "meeting_name",
            "date",
            "location",
            "participants",
            "materials",
            "agenda_summary",
            "agenda_items",
            "decisions",
            "next_topics",
            "next_date",
            "next_location"
        ]
    }
}

SYSTEM_PROMPT = """あなたは議事録作成の専門家です。
会議の文字起こしと会議資料（アジェンダ）をもとに、議事録データを構造化して抽出してください。

抽出ルール:
- 発言内容は要点のみ。冗長な言い回しは省く
- 決定事項は「〜とする」の形で簡潔に記述
- 議題は資料のアジェンダ順に沿う。資料がない場合は文脈から判断
- 出席者は会社・組織ごとにグループ化し、発言者として登場した人物名を抽出（敬称略）
- 議事次第は「１．〇〇」の番号付き形式で
- 不明な情報は無理に埋めず空にする"""


def extract_minutes(transcript: str, agenda_text: str = "",
                    location_override: str = "") -> dict:
    """
    文字起こしテキストとアジェンダテキストから議事録データを抽出する。

    Args:
        transcript: 会議の文字起こしテキスト
        agenda_text: 会議資料から抽出したアジェンダテキスト（任意）
        location_override: アプリUIで入力された場所（指定時はAI抽出値を上書き）

    Returns:
        議事録の構造化データ（dict）
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません。.env ファイルを確認してください。")

    client = anthropic.Anthropic(api_key=api_key)

    user_content = "## 会議の文字起こし\n\n" + transcript.strip()
    if agenda_text:
        user_content = "## 会議資料（アジェンダ）\n\n" + agenda_text.strip() + "\n\n" + user_content

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[MINUTES_SCHEMA],
        tool_choice={"type": "tool", "name": "extract_minutes"},
        messages=[{"role": "user", "content": user_content}]
    )

    # tool_useブロックからJSON取得
    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_minutes":
            result = block.input
            # UI入力の場所で上書き
            if location_override:
                result["location"] = location_override
            return result

    raise RuntimeError("LLMからの構造化データ取得に失敗しました。")


if __name__ == "__main__":
    # 動作確認用サンプル実行（APIキー設定後に実行）
    sample_transcript = """
田中: では始めましょう。今日は第3回プロジェクト定例です。場所は本社会議室Aです。
山田: よろしくお願いします。
田中: まず前回のアクションの確認から。山田さん、仕様書の進捗はどうですか？
山田: 8割できています。今週中に完成させます。
田中: ありがとうございます。次にシステム設計の話に移りましょう。
佐藤: データベースはPostgreSQLを使う方向で検討しています。
田中: それで行きましょう。決定事項として記録してください。
山田: 開発環境についてはDockerを使うことにしましょうか。
田中: 賛成です。では開発環境はDockerで統一ということで決定。
佐藤: 次回は来週水曜日でよろしいでしょうか？
田中: はい、それで問題ありません。令和8年7月29日の14時からで。次回の議題は詳細設計のレビューをお願いします。
"""
    sample_agenda = """
資料1 システム設計案（田中作成）
資料2 開発スケジュール（山田作成）

議事次第
１．前回アクションの確認
２．システム設計について
３．開発環境の決定
４．次回スケジュール確認
"""
    result = extract_minutes(sample_transcript, sample_agenda, location_override="本社会議室A")
    print(json.dumps(result, ensure_ascii=False, indent=2))
