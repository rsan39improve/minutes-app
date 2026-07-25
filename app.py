"""
議事録自動生成アプリ - Streamlit メイン画面
文字起こしテキスト + 会議資料PDF をアップロードして
固定様式の Word ファイルをダウンロードする。
"""

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from extractor import extract_text_from_pdf, extract_text_from_txt
from llm_client import extract_minutes
from word_builder import build_minutes_docx

load_dotenv()

# ===== ページ設定 =====
st.set_page_config(
    page_title="議事録自動生成",
    page_icon="📋",
    layout="centered",
)

# ===== スタイル =====
st.markdown(
    """
    <style>
    .main {max-width: 720px; margin: 0 auto;}
    .stButton > button {
        width: 100%;
        background-color: #1F497D;
        color: white;
        font-size: 1.1rem;
        padding: 0.6rem 1rem;
        border-radius: 8px;
        border: none;
    }
    .stButton > button:hover {background-color: #2e6aab;}
    .upload-box {
        border: 2px dashed #BDD7EE;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== ヘッダー =====
st.title("📋 議事録自動生成")
st.caption("文字起こしテキスト + 会議資料PDFをアップして、Wordファイルを受け取るだけ。")

st.divider()

# ===== APIキー確認 =====
api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
if not api_key:
    st.warning(
        "⚠️ ANTHROPIC_API_KEY が設定されていません。"
        "`.env` ファイルに API キーを追加してください。"
    )

# ===== ファイルアップロード =====
col1, col2 = st.columns(2)

with col1:
    st.subheader("① 文字起こしテキスト")
    transcript_file = st.file_uploader(
        "iPhoneアプリが生成したテキストファイル",
        type=["txt", "docx"],
        key="transcript",
        help="録音アプリが出力した文字起こしのテキストファイル（.txt）をアップしてください。",
    )

with col2:
    st.subheader("② 会議資料（任意）")
    agenda_file = st.file_uploader(
        "当日のアジェンダ・資料PDF",
        type=["pdf"],
        key="agenda",
        help="事前に用意した会議資料のPDF。なければ文字起こしだけで処理します。",
    )

st.divider()

# ===== プレビュー（アップ後に表示）=====
if transcript_file:
    with st.expander("文字起こし内容を確認する", expanded=False):
        try:
            text_preview = extract_text_from_txt(transcript_file.read())
            transcript_file.seek(0)
            st.text_area("", text_preview[:1500] + ("..." if len(text_preview) > 1500 else ""), height=200)
        except Exception as e:
            st.error(f"テキスト読み込みエラー: {e}")

# ===== 生成ボタン =====
generate_disabled = transcript_file is None or not api_key
btn_label = "📝 議事録 Word を生成する" if not generate_disabled else "📝 議事録 Word を生成する（ファイルをアップしてください）"

if st.button(btn_label, disabled=generate_disabled, type="primary"):
    with st.spinner("AIが議事録を解析中... しばらくお待ちください"):
        try:
            # テキスト抽出
            transcript_bytes = transcript_file.read()
            transcript_text = extract_text_from_txt(transcript_bytes)

            agenda_text = ""
            if agenda_file:
                agenda_bytes = agenda_file.read()
                agenda_text = extract_text_from_pdf(agenda_bytes)

            # LLM で構造化データ抽出
            with st.spinner("AIが内容を解析中..."):
                minutes_data = extract_minutes(transcript_text, agenda_text)

            # Word ファイル生成
            with st.spinner("Wordファイルを生成中..."):
                docx_bytes = build_minutes_docx(minutes_data)

            st.success("✅ 議事録の生成が完了しました！")

            # ===== 内容プレビュー =====
            with st.expander("抽出された内容を確認する", expanded=True):
                st.markdown(f"**会議名**: {minutes_data.get('meeting_name', '')}")
                st.markdown(f"**開催日時**: {minutes_data.get('date', '') or '不明'}")
                st.markdown(f"**参加者**: {', '.join(minutes_data.get('participants', []))}")

                if minutes_data.get("agenda_items"):
                    st.markdown("**議題・議論内容**")
                    for item in minutes_data["agenda_items"]:
                        st.markdown(f"- **{item['title']}**: {item['discussion']}")

                if minutes_data.get("decisions"):
                    st.markdown("**決定事項**")
                    for d in minutes_data["decisions"]:
                        st.markdown(f"- {d}")

                if minutes_data.get("next_topics"):
                    st.markdown("**次回議題**")
                    for t in minutes_data["next_topics"]:
                        st.markdown(f"- {t}")

                if minutes_data.get("next_date"):
                    st.markdown(f"**次回開催**: {minutes_data['next_date']}")

            # ===== ダウンロードボタン =====
            date_str = datetime.now().strftime("%Y%m%d")
            meeting_name = minutes_data.get("meeting_name", "会議") or "会議"
            filename = f"{date_str}_{meeting_name}_議事録.docx"

            st.download_button(
                label="⬇️ Wordファイルをダウンロード",
                data=docx_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        except ValueError as e:
            st.error(f"設定エラー: {e}")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            st.info("文字起こしファイルの内容、またはAPIキーを確認してください。")

# ===== フッター =====
st.divider()
st.caption(
    "※ アップロードされたファイルはサーバーに保存されません。"
    "　処理は都度完結します。"
)
