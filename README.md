# 議事録自動生成アプリ

文字起こしテキスト + 会議資料PDFをアップするだけで、固定様式のWordファイルを出力するWebアプリ。

## セットアップ

```bash
# 1. 依存ライブラリをインストール
pip3 install -r requirements.txt

# 2. APIキーを設定
cp .env.example .env
# .envを開いて ANTHROPIC_API_KEY に自分のAPIキーを入力

# 3. アプリ起動
streamlit run app.py
```

ブラウザが自動で開きます（http://localhost:8501）。

## 使い方

1. **文字起こしテキスト**（.txt）をアップロード
2. **会議資料PDF**（任意）をアップロード
3. 「議事録Wordを生成する」をクリック
4. 内容を確認してWordをダウンロード

## POC動作確認

```bash
# POC① LLM→JSON変換の確認
python3 llm_client.py

# POC② PDF抽出の確認
python3 extractor.py 会議資料.pdf

# POC③ Word生成の確認
python3 word_builder.py
# → sample_minutes.docx が生成される
```

## ファイル構成

```
minutes-app/
├── app.py           # Streamlit メイン
├── extractor.py     # PDF・テキスト抽出
├── llm_client.py    # LLM呼び出し（JSON Schema強制）
├── word_builder.py  # Word生成
├── requirements.txt
├── .env.example
└── README.md
```

## デプロイ（Streamlit Cloud）

1. このフォルダをGitHubリポジトリにpush
2. [share.streamlit.io](https://share.streamlit.io) でリポジトリを接続
3. Secrets に `ANTHROPIC_API_KEY` を設定
4. チームにURLを共有するだけ
