# 議事録自動作成ツール

Synclogの話者ラベル付き文字起こしから、会社ひな型に沿ったWord議事録を生成するNext.jsアプリです。アプリ本体は `web/` にあります。

- 公開URL: https://minutes-app-next.vercel.app
- AIは議事本文のみを再構成
- 開催日時・場所・出席者・資料名は空欄で出力し、担当者がWordで記入

## 技術構成

| 技術 | 役割 |
|---|---|
| Next.js / React | 画面とサーバーAPI |
| TypeScript | アプリの処理 |
| CSS | 現在の画面デザイン |
| Tailwind CSS | 導入済み（現状はほぼ未使用） |
| Claude API | 議事本文の構造化 |
| Mammoth / pdf-parse | Word・PDFからの文字抽出 |
| JSZip / XML | 会社ひな型docxの編集 |
| Vercel | 公開・環境変数の保管 |

shadcn/uiは使用していません。

## ローカル起動

```bash
cd web
npm install
cp .env.example .env.local
```

`web/.env.local` に次を設定します。

```text
ANTHROPIC_API_KEY=...
APP_ACCESS_PASSWORD=...
```

起動します。

```bash
npm run dev
```

ブラウザで http://localhost:3000 を開きます。

## 使い方

1. パスワードで入室
2. 発言ログを貼り付け（または `.txt` / `.docx` をアップロード）
3. 必要なら打合せ次第・その他資料を追加
4. 「議事録を作成する」を押す
5. プレビューと `[要確認]` を確認
6. Wordをダウンロードし、日時・出席者などを記入

## ファイル構成

```text
web/
├── src/app/                 # 画面・API
├── src/components/          # ログイン・議事録画面
├── src/lib/                 # 認証・抽出・Claude・数値照合・Word生成
├── assets/議事録ひな型.docx # ひな型の正本
├── prompts/minutes.txt      # AI指示書の正本
├── .env.example
└── package.json
```

詳細は `web/README.md` を参照してください。

## Vercelへの反映

```bash
cd web
npm run build
vercel deploy --prod
```

Vercelには次の環境変数が必要です。

- `ANTHROPIC_API_KEY`
- `APP_ACCESS_PASSWORD`
