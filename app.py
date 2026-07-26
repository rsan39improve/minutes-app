"""
議事録自動生成ツール - Streamlit メイン画面
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
    page_title="議事録自動作成ツール",
    page_icon="📋",
    layout="centered",
)

# ===== スタイル =====
st.markdown(
    """
    <style>
    .block-container {max-width: 780px; padding-top: 1.8rem;}

    /* メインボタン */
    .stButton {padding-left: 0 !important; padding-right: 0 !important;}
    .stButton > button {
        width: 100%;
        background-color: #1a1a1a;
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: bold;
        padding: 0.75rem 1rem;
        border-radius: 5px;
        border: none;
        letter-spacing: 0.05em;
        display: block;
    }
    .stButton > button:hover {background-color: #3a3a3a;}
    .stButton > button:disabled {background-color: #aaaaaa; color: #eeeeee;}

    /* ボタン行の余白を除去して横幅を揃える */
    div[data-testid="column"] .stButton > button,
    .element-container .stButton > button {
        margin-left: 0;
        margin-right: 0;
    }

    /* ダウンロードボタン */
    .stDownloadButton > button {
        width: 100%;
        background-color: #1e6f3e;
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: bold;
        padding: 0.7rem 1rem;
        border-radius: 5px;
        border: none;
    }
    .stDownloadButton > button:hover {background-color: #258a4e;}

    /* セクション区切り */
    hr {border-color: #dddddd;}

    /* ラベル */
    label {font-weight: 600 !important;}

    /* ファイルアップローダーの英語テキストを日本語に上書き */
    /* ドラッグ＆ドロップテキスト部分を非表示 */
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span {
        display: none !important;
    }
    /* 上書き表示 */
    [data-testid="stFileUploaderDropzone"]::before {
        content: 'ここにファイルをドラッグ＆ドロップ';
        display: block;
        text-align: center;
        color: #666666;
        font-size: 0.9rem;
        padding: 0.6rem 0 0.3rem 0;
    }
    /* "Browse files" ボタン文字を非表示にして日本語で上書き */
    [data-testid="stFileUploaderDropzone"] button {
        font-size: 0 !important;
        color: transparent !important;
    }
    [data-testid="stFileUploaderDropzone"] button::after {
        content: 'ファイルを選択';
        font-size: 0.875rem;
        color: #333333;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ===== ヘッダー =====
st.title("📋 議事録自動作成ツール")
st.caption("ファイルをアップしてボタンを押すだけで、議事録ファイルが完成します。")

st.divider()

# ===== APIキー確認 =====
api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", "")
if not api_key:
    st.warning("⚠️ 管理者設定が未完了のため、現在使用できません。管理者にお問い合わせください。")

# ===== 入力エリア =====
st.subheader("入力情報")

# ── ファイルアップロード ──
col1, col2 = st.columns(2)
with col1:
    st.markdown("**① 文字起こしテキスト** （必須）")
    transcript_file = st.file_uploader(
        "録音アプリが出力したテキストファイル",
        type=["txt", "docx"],
        key="transcript",
    )
with col2:
    st.markdown("**② 会議資料** （任意）")
    agenda_file = st.file_uploader(
        "当日の会議資料を貼り付けてください。",
        type=["pdf"],
        key="agenda",
    )

st.markdown("")

# ── テキスト入力 ──
col3, col4 = st.columns(2)
with col3:
    location_input = st.text_input(
        "③ 開催場所",
        placeholder="例：本社会議室A　／　オンライン会議",
    )
with col4:
    district_input = st.text_input(
        "④ 地区名",
        placeholder="例：○○地区",
        help="Wordファイルのページ上部（ヘッダー）に表示されます。",
    )

meeting_name_input = st.text_input(
    "⑤ 会議名（任意・AIが自動推測します）",
    placeholder="例：第3回プロジェクト定例打合せ　　← 空欄でもAIが文字起こしから推測します",
    help="入力した場合、AIの推測より優先されます。",
)

st.divider()

# ===== プレビュー =====
if transcript_file:
    with st.expander("会議内容を確認する", expanded=False):
        try:
            text_preview = extract_text_from_txt(transcript_file.read())
            transcript_file.seek(0)
            st.text_area(
                "",
                text_preview[:1500] + ("..." if len(text_preview) > 1500 else ""),
                height=160,
            )
        except Exception as e:
            st.error(f"テキスト読み込みエラー: {e}")

# ===== 生成ボタン =====
generate_disabled = transcript_file is None or not api_key

st.button(
    "📝 議事録を作成する",
    disabled=generate_disabled,
    key="generate_btn",
    type="primary",
)

if st.session_state.get("generate_btn"):
    with st.spinner("AIが議事録を解析中... しばらくお待ちください（30秒〜1分程度）"):
        try:
            transcript_bytes = transcript_file.read()
            transcript_text = extract_text_from_txt(transcript_bytes)

            agenda_text = ""
            if agenda_file:
                agenda_bytes = agenda_file.read()
                agenda_text = extract_text_from_pdf(agenda_bytes)

            minutes_data = extract_minutes(
                transcript_text,
                agenda_text,
                location_override=location_input.strip(),
            )

            # 会議名を手動入力で上書き
            if meeting_name_input.strip():
                minutes_data["meeting_name"] = meeting_name_input.strip()

            docx_bytes = build_minutes_docx(
                minutes_data,
                district=district_input.strip(),
            )

            st.success("✅ 議事録の生成が完了しました！")

            # ── 内容プレビュー ──
            with st.expander("抽出された内容を確認する", expanded=True):
                st.markdown(f"**会議名**: {minutes_data.get('meeting_name', '')}")
                st.markdown(f"**開催日時**: {minutes_data.get('date', '') or '不明'}")
                st.markdown(f"**場所**: {minutes_data.get('location', '') or '不明'}")

                participants = minutes_data.get("participants", [])
                if participants:
                    st.markdown("**出席者**")
                    for p in participants:
                        st.markdown(f"- {p.get('organization', '')}：{p.get('names', '')}")

                if minutes_data.get("materials"):
                    st.markdown("**資料**")
                    for m in minutes_data["materials"]:
                        st.markdown(f"- {m}")

                if minutes_data.get("agenda_items"):
                    st.markdown("**議題・議論内容**")
                    for item in minutes_data["agenda_items"]:
                        st.markdown(f"- **{item['title']}**: {item['discussion']}")

                if minutes_data.get("decisions"):
                    st.markdown("**決定事項**")
                    for d in minutes_data["decisions"]:
                        st.markdown(f"- {d}")

                if minutes_data.get("next_date"):
                    st.markdown(f"**次回開催**: {minutes_data['next_date']}")

            # ── ダウンロードボタン ──
            date_str = datetime.now().strftime("%Y%m%d")
            meeting_name = minutes_data.get("meeting_name", "会議") or "会議"
            filename = f"{date_str}_{meeting_name}_議事録.docx"

            st.download_button(
                label="⬇️ 議事録ファイルをダウンロード",
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
st.caption("※ アップロードされたファイルはサーバーに保存されません。処理は都度完結します。")
