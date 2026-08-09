# 議事録自動生成アプリ

Synclogの話者ラベル付き文字起こし（＋任意で当日資料・打合せ次第）から、
会社ひな型に沿ったWord議事録を生成するWebアプリ。

AIは**議事本文のみ**を再構成します。開催日時・場所・出席者・資料名は空欄のまま出力し、担当者がWordで記入します。

## セットアップ

```bash
# 1. 依存ライブラリをインストール
pip3 install -r requirements.txt

# 2. 環境変数を設定
cp .env.example .env
# .env を開き次を設定:
#   ANTHROPIC_API_KEY=...
#   APP_ACCESS_PASSWORD=...

# 3. アプリ起動
streamlit run app.py
```

ブラウザが自動で開きます（http://localhost:8501）。

## 使い方

1. パスワードで入室
2. **発言ログ**を貼り付け（または .txt / .docx をアップロード）
3. 必要なら当日資料・打合せ次第を追加（任意）
4. 「議事録を作成する」→ 画面で `[要確認]` を確認
5. Wordをダウンロードし、ヘッダー（日時・出席者等）を記入して完成

## ファイル構成

```
minutes-app/
├── app.py              # Streamlit UI・認証
├── llm_client.py       # Claude API（構造化JSON）
├── word_builder.py     # ひな型.docx編集
├── extractor.py        # テキスト抽出
├── number_check.py     # 数値の機械照合
├── prompts/minutes.txt # システムプロンプト
├── 議事録ひな型.docx
├── requirements.txt
└── .env.example
```

## デプロイ（Streamlit Cloud）

1. このフォルダをGitHubリポジトリにpush（`議事録ひな型.docx` を含める）
2. [share.streamlit.io](https://share.streamlit.io) でリポジトリを接続
3. Secrets に設定:
   - `ANTHROPIC_API_KEY`
   - `APP_ACCESS_PASSWORD`
4. 再デプロイ後、パスワードなしでは入力画面に到達できないことを確認
