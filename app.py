"""
議事録自動生成ツール - Streamlit メイン画面
Synclogの発言ログ（貼り付け or ファイル）と打合せ次第・その他資料から
会社ひな型の Word を生成する。
"""

from __future__ import annotations

import os
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from extractor import extract_text_from_upload, normalize_transcript
from llm_client import extract_minutes
from number_check import apply_number_check, collect_confirmation_tags
from word_builder import build_minutes_docx

load_dotenv()

SESSION_TTL_SEC = 24 * 60 * 60  # 24時間

st.set_page_config(
    page_title="議事録自動作成ツール",
    page_icon="📋",
    layout="centered",
)

# ===== スタイル =====
st.markdown(
    """
    <style>
    :root {
        --bg: #f5f2ee;
        --surface: #ffffff;
        --surface-2: #efece5;
        --border: #e2ddd3;
        --border-strong: #cdc5b7;
        --text: #1c1815;
        --text-muted: #6f6a60;
        --text-faint: #948d80;
        --accent: #d63d13;
        --accent-hover: #e94a1f;
        --success: #1c8a5c;
        --success-hover: #23a56f;
        --warn: #b45309;
    }

    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"],
    .main {
        background-color: var(--bg) !important;
        color: var(--text);
    }
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
            "Hiragino Kaku Gothic ProN", "Yu Gothic UI", "Noto Sans JP", sans-serif !important;
    }

    /* 上部の白い帯を消し、ページと一体に見せる */
    header[data-testid="stHeader"],
    .stApp > header {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu,
    footer,
    .stDeployButton {
        display: none !important;
        visibility: hidden !important;
    }
    /* ヘッダー領域の白背景が残らないようにする */
    header[data-testid="stHeader"] * {
        background: transparent !important;
    }

    /* 見出し横のリンク（鎖）アイコンをすべて非表示 */
    [data-testid="stHeaderActionElements"],
    [data-testid="stHeadingWithActionElements"] a,
    .stHeadingWithActionElements a,
    h1 a,
    h2 a,
    h3 a {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }

    .block-container {max-width: 760px; padding-top: 1.6rem;}

    h1 {
        font-size: 2rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.01em;
        color: var(--text) !important;
    }
    [data-testid="stCaptionContainer"] { color: var(--text-faint) !important; }

    h3 {
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-muted) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface);
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        margin-bottom: 12px;
    }
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        background: var(--surface) !important;
    }
    [data-testid="stAlert"] { border-radius: 10px !important; }

    /* メインボタンは上の区切り線と同じ全幅に揃える */
    div[data-testid="stButton"],
    .stButton,
    .stButton > div {
        width: 100% !important;
    }
    .stButton > button,
    button[data-testid="baseButton-primary"],
    button[kind="primary"] {
        width: 100% !important;
        max-width: 100% !important;
        background: linear-gradient(180deg, var(--accent-hover) 0%, var(--accent) 100%);
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 700;
        padding: 0.8rem 1rem;
        border-radius: 10px;
        border: none;
        letter-spacing: 0.02em;
        display: block !important;
        box-shadow: 0 8px 24px -8px rgba(214, 61, 19, 0.45);
    }
    .stButton > button:hover,
    button[data-testid="baseButton-primary"]:hover,
    button[kind="primary"]:hover {filter: brightness(1.06);}
    .stButton > button:disabled,
    button[data-testid="baseButton-primary"]:disabled,
    button[kind="primary"]:disabled {
        background: var(--border-strong);
        color: #ffffff;
        box-shadow: none;
    }

    /* 退出: オレンジボタンではなく細い文字リンク（全幅ルールの対象外） */
    div[data-testid="column"] div[data-testid="stButton"],
    div[data-testid="column"] .stButton,
    div[data-testid="column"] .stButton > div {
        width: auto !important;
    }
    .stButton > button[kind="secondary"],
    button[data-testid="baseButton-secondary"] {
        width: auto !important;
        margin-left: auto !important;
        background: transparent !important;
        color: var(--text-muted) !important;
        font-size: 0.84rem !important;
        font-weight: 500 !important;
        padding: 0.35rem 0.2rem !important;
        border-radius: 0 !important;
        border: none !important;
        box-shadow: none !important;
        letter-spacing: 0.04em;
        text-decoration: underline;
        text-underline-offset: 3px;
        display: inline-block !important;
    }
    .stButton > button[kind="secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover {
        filter: none !important;
        color: var(--text) !important;
        background: transparent !important;
    }

    .stDownloadButton > button {
        width: 100%;
        background-color: var(--success);
        color: #ffffff;
        font-size: 1.0rem;
        font-weight: 700;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        border: none;
    }
    .stDownloadButton > button:hover {background-color: var(--success-hover);}

    hr {border-color: var(--border) !important;}
    label {font-weight: 600 !important; color: var(--text) !important;}

    .stTextInput input, .stTextArea textarea {
        background-color: var(--surface-2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
    }

    [data-testid="stFileUploaderDropzone"] {
        background-color: var(--surface-2) !important;
        border: 1px dashed var(--border-strong) !important;
        border-radius: 9px !important;
    }
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span { display: none !important; }
    [data-testid="stFileUploaderDropzone"]::before {
        content: 'ここにファイルをドラッグ＆ドロップ';
        display: block;
        text-align: center;
        color: var(--text-faint);
        font-size: 0.9rem;
        padding: 0.6rem 0 0.3rem 0;
    }
    [data-testid="stFileUploaderDropzone"] button {
        font-size: 0 !important;
        color: transparent !important;
    }
    [data-testid="stFileUploaderDropzone"] button::after {
        content: 'ファイルを選択';
        font-size: 0.875rem;
        color: var(--text);
    }

    .confirm-box {
        background: #fff7ed;
        border: 1px solid #fdba74;
        border-radius: 10px;
        padding: 0.9rem 1rem;
        margin: 0.6rem 0 1rem 0;
    }
    .confirm-box strong { color: var(--warn); }
    </style>
    """,
    unsafe_allow_html=True,
)


def _get_secret(name: str) -> str:
    env_val = os.getenv(name, "")
    if env_val:
        return env_val
    try:
        return st.secrets.get(name, "") or ""
    except Exception:
        return ""


def _is_authenticated() -> bool:
    if not st.session_state.get("auth_ok"):
        return False
    ts = st.session_state.get("auth_ts")
    if not ts:
        return False
    if time.time() - float(ts) > SESSION_TTL_SEC:
        st.session_state.auth_ok = False
        st.session_state.auth_ts = None
        return False
    return True


def render_login() -> None:
    st.title("📋 議事録自動作成ツール")
    st.caption("社内限定ツールです。パスワードを入力してください。")
    st.divider()

    expected = _get_secret("APP_ACCESS_PASSWORD")
    if not expected:
        st.warning("⚠️ 管理者設定（アクセスパスワード）が未完了のため、現在使用できません。")
        return

    with st.form("login_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("入室する", type="primary")
        if submitted:
            if password == expected:
                st.session_state.auth_ok = True
                st.session_state.auth_ts = time.time()
                st.rerun()
            else:
                st.error("パスワードが正しくありません。")


def _input_block(
    title: str,
    key_prefix: str,
    *,
    required: bool,
    file_types: list[str],
    paste_placeholder: str = "",
    allow_paste: bool = True,
) -> tuple[str, list[str]]:
    """
    入力ブロック。
    allow_paste=True のとき貼り付け/ファイル切替、False のときファイルのみ。
    Returns: (text, warnings)
    """
    warnings: list[str] = []
    req_label = "必須" if required else "任意"
    with st.container(border=True):
        st.markdown(f"**{title}** （{req_label}）")
        text = ""
        if allow_paste:
            method = st.radio(
                "入力方法",
                ["直接貼り付け", "ファイルをアップロード"],
                horizontal=True,
                key=f"{key_prefix}_method",
                label_visibility="collapsed",
            )
            if method == "直接貼り付け":
                text = st.text_area(
                    "テキスト",
                    height=180 if required else 120,
                    placeholder=paste_placeholder,
                    key=f"{key_prefix}_paste",
                    label_visibility="collapsed",
                )
            else:
                uploaded = st.file_uploader(
                    "ファイル",
                    type=file_types,
                    key=f"{key_prefix}_file",
                    label_visibility="collapsed",
                )
                if uploaded is not None:
                    extracted, warn = extract_text_from_upload(
                        uploaded.read(), uploaded.name
                    )
                    if warn:
                        warnings.append(warn)
                    text = extracted or ""
        else:
            uploaded = st.file_uploader(
                "ファイル",
                type=file_types,
                key=f"{key_prefix}_file",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                extracted, warn = extract_text_from_upload(
                    uploaded.read(), uploaded.name
                )
                if warn:
                    warnings.append(warn)
                text = extracted or ""
    return (text or "").strip(), warnings


def render_preview(minutes_data: dict) -> None:
    confirms = collect_confirmation_tags(minutes_data)
    if confirms:
        st.markdown(
            f'<div class="confirm-box"><strong>要確認が {len(confirms)} 箇所あります。</strong>'
            f"<br>Wordファイルダウンロード後に確認してください。</div>",
            unsafe_allow_html=True,
        )
        with st.expander("要確認一覧", expanded=False):
            for c in confirms:
                st.markdown(f"- `{c}`")
    else:
        st.success("要確認タグは検出されませんでした。念のため本文も確認してください。")

    with st.expander("議事録内容プレビュー", expanded=False):
        for topic in minutes_data.get("議題") or []:
            st.markdown(f"### {topic.get('番号', '')}{topic.get('見出し', '')}")
            for sub in topic.get("小項目") or []:
                st.markdown(f"**{sub.get('番号', '')}{sub.get('見出し', '')}**")
                if sub.get("説明"):
                    st.markdown(sub["説明"])
                for qa in sub.get("質疑") or []:
                    speaker = qa.get("話者", "")
                    st.markdown(f"- 質問（話者:{speaker}）: {qa.get('質問', '')}")
                    st.markdown(f"- 回答: －{qa.get('回答', '').lstrip('－').lstrip('-')}")
        st.markdown(f"**次回打合せ：** {minutes_data.get('次回打合せ', '')}")
        st.markdown("以上")


def render_app() -> None:
    head_l, head_r = st.columns([6, 1], vertical_alignment="top")
    with head_l:
        st.title("📋 議事録自動作成ツール")
        st.caption("Synclogの文字起こしデータを貼り付け、ボタンを押すと議事録が作成できます。")
    with head_r:
        st.markdown("<div style='height: 0.85rem'></div>", unsafe_allow_html=True)
        if st.button("退出", key="logout_btn", type="secondary"):
            st.session_state.auth_ok = False
            st.session_state.auth_ts = None
            st.rerun()

    st.divider()

    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning("⚠️ 管理者設定（APIキー）が未完了のため、現在使用できません。")

    # Streamlit secrets / .env を llm_client が見られるよう環境へ反映
    if api_key and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = api_key

    st.subheader("入力情報")

    transcript, tw = _input_block(
        "① 発言ログ（文字起こし）",
        "transcript",
        required=True,
        file_types=["txt", "docx"],
        paste_placeholder="Synclogからコピーした話者ラベル付き文字起こしを貼り付けてください",
    )
    agenda, aw = _input_block(
        "② 打合せ次第",
        "agenda",
        required=False,
        file_types=["txt", "docx", "pdf"],
        paste_placeholder="会議の次第があれば貼り付けてください（なければ空のままでOK）",
    )
    materials, mw = _input_block(
        "③ その他資料",
        "materials",
        required=False,
        file_types=["pdf", "docx", "txt"],
        allow_paste=False,
    )

    all_warnings = tw + mw + aw
    for w in all_warnings:
        st.warning(w)

    st.caption("※ 開催日時・場所・出席者・資料名などは担当者が直接記入してください。")
    st.divider()

    can_submit = bool(transcript) and bool(api_key)
    clicked = st.button(
        "📝 議事録を作成する",
        disabled=not can_submit,
        key="generate_btn",
        type="primary",
    )

    if clicked and can_submit:
        with st.spinner("AIが議事録を再構成中... しばらくお待ちください（30秒〜1分程度）"):
            try:
                transcript_text = normalize_transcript(transcript)
                # 資料・次第は空でも可。警告付きで空になったものは空文字として送る
                minutes_data = extract_minutes(
                    transcript_text,
                    materials=materials,
                    agenda=agenda,
                )
                minutes_data = apply_number_check(minutes_data, transcript_text)
                docx_bytes = build_minutes_docx(minutes_data)

                st.session_state["last_minutes"] = minutes_data
                st.session_state["last_docx"] = docx_bytes
                st.session_state["last_filename"] = (
                    f"{datetime.now().strftime('%Y%m%d')}_議事録.docx"
                )
                st.success("✅ 議事録の作成が完了しました。内容を確認してからダウンロードしてください。")
            except ValueError as e:
                st.error(f"入力エラー: {e}")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                st.info("発言ログの内容、または管理者設定を確認してください。")

    if st.session_state.get("last_minutes") and st.session_state.get("last_docx"):
        render_preview(st.session_state["last_minutes"])
        st.download_button(
            label="⬇️ 議事録ファイルをダウンロード",
            data=st.session_state["last_docx"],
            file_name=st.session_state.get("last_filename", "議事録.docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    st.divider()
    st.caption("※ 入力データはサーバーに保存されません。処理は都度完結します。")


# ===== エントリ =====
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False
if "auth_ts" not in st.session_state:
    st.session_state.auth_ts = None

if _is_authenticated():
    render_app()
else:
    render_login()
