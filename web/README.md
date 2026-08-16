# 議事録自動作成ツール

この `web/` にアプリ本体があります。

- 公開URL: https://minutes-app-next.vercel.app
- ひな型とAI指示書を更新する場合は、`web/assets` と `web/prompts` を更新します

## 起動

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

`.env.local` に `ANTHROPIC_API_KEY` と `APP_ACCESS_PASSWORD` を設定してください。

ブラウザで http://localhost:3000

## 構成

| パス | 役割 |
|---|---|
| `src/app` | 画面・APIルート |
| `src/components` | ログイン・入力・プレビュー画面 |
| `src/lib` | 認証 / 抽出 / Claude / 要確認 / Word生成 |
| `assets/議事録ひな型.docx` | 会社ひな型の正本 |
| `prompts/minutes.txt` | AIシステムプロンプトの正本 |

## 確認コマンド

```bash
npm run build
npm audit --omit=dev
```

## Vercel

Vercelプロジェクト名は `minutes-app-next` です。

```bash
vercel deploy --prod
```

必要な環境変数:

- `ANTHROPIC_API_KEY`
- `APP_ACCESS_PASSWORD`
