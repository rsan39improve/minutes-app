"use client";

import { FormEvent, useMemo, useState } from "react";
import type { MinutesData } from "@/lib/types";

type InputMode = "paste" | "file";

type GenerateResponse = {
  minutes?: MinutesData;
  confirms?: string[];
  warnings?: string[];
  filename?: string;
  docxBase64?: string;
  error?: string;
};

type Props = {
  apiConfigured: boolean;
  onLogout: () => void;
};

function InputBlock(props: {
  title: string;
  required: boolean;
  allowPaste: boolean;
  pastePlaceholder: string;
  accept: string;
  uploadFormats: string;
  mode: InputMode;
  text: string;
  file: File | null;
  onMode: (m: InputMode) => void;
  onText: (v: string) => void;
  onFile: (f: File | null) => void;
}) {
  const {
    title,
    required,
    allowPaste,
    pastePlaceholder,
    accept,
    uploadFormats,
    mode,
    text,
    file,
    onMode,
    onText,
    onFile,
  } = props;

  return (
    <section className="card">
      <h3>
        {title}（{required ? "必須" : "任意"}）
      </h3>
      {allowPaste ? (
        <div className="mode-row">
          <label>
            <input
              type="radio"
              checked={mode === "file"}
              onChange={() => onMode("file")}
            />
            ファイルをアップロード（{uploadFormats}）
          </label>
          <label>
            <input
              type="radio"
              checked={mode === "paste"}
              onChange={() => onMode("paste")}
            />
            直接貼り付け
          </label>
        </div>
      ) : (
        <div className="mode-row">
          <span>ファイルをアップロード（{uploadFormats}）</span>
        </div>
      )}

      {allowPaste && mode === "paste" ? (
        <textarea
          className="textarea"
          placeholder={pastePlaceholder}
          value={text}
          onChange={(e) => onText(e.target.value)}
          rows={required ? 8 : 5}
        />
      ) : (
        <div className="file-row">
          <input
            type="file"
            accept={accept}
            onChange={(e) => onFile(e.target.files?.[0] || null)}
          />
          {file ? <span className="file-name">{file.name}</span> : null}
        </div>
      )}
    </section>
  );
}

export function MinutesApp({ apiConfigured, onLogout }: Props) {
  const [transcriptMode, setTranscriptMode] = useState<InputMode>("file");
  const [agendaMode, setAgendaMode] = useState<InputMode>("file");
  const [transcriptText, setTranscriptText] = useState("");
  const [agendaText, setAgendaText] = useState("");
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [agendaFile, setAgendaFile] = useState<File | null>(null);
  const [materialsFile, setMaterialsFile] = useState<File | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [minutes, setMinutes] = useState<MinutesData | null>(null);
  const [confirms, setConfirms] = useState<string[]>([]);
  const [docxBase64, setDocxBase64] = useState<string | null>(null);
  const [filename, setFilename] = useState("議事録.docx");

  const canSubmit = useMemo(() => {
    const hasTranscript =
      (transcriptMode === "paste" && transcriptText.trim().length > 0) ||
      (transcriptMode === "file" && !!transcriptFile);
    return hasTranscript && apiConfigured && !loading;
  }, [transcriptMode, transcriptText, transcriptFile, apiConfigured, loading]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setWarnings([]);
    setLoading(true);
    try {
      const form = new FormData();
      if (transcriptMode === "paste") {
        form.set("transcriptText", transcriptText);
      } else if (transcriptFile) {
        form.set("transcriptFile", transcriptFile);
      }
      if (agendaMode === "paste") {
        form.set("agendaText", agendaText);
      } else if (agendaFile) {
        form.set("agendaFile", agendaFile);
      }
      if (materialsFile) {
        form.set("materialsFile", materialsFile);
      }

      const res = await fetch("/api/generate", { method: "POST", body: form });
      const data = (await res.json()) as GenerateResponse;
      if (!res.ok) {
        setError(data.error || "作成に失敗しました。");
        setWarnings(data.warnings || []);
        return;
      }
      setMinutes(data.minutes || null);
      setConfirms(data.confirms || []);
      setWarnings(data.warnings || []);
      setDocxBase64(data.docxBase64 || null);
      setFilename(data.filename || "議事録.docx");
    } catch {
      setError("通信エラーが発生しました。");
    } finally {
      setLoading(false);
    }
  }

  function downloadDocx() {
    if (!docxBase64) return;
    const bin = atob(docxBase64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="panel">
      <header className="topbar topbar-row">
        <div>
          <div className="brand-row">
            <h1 className="brand">議事録自動作成ツール</h1>
            <span className="badge">Internal</span>
          </div>
          <p className="caption">
            会議の文字起こしデータを貼り付け、ボタンを押すと議事録が作成できます。
          </p>
        </div>
        <button type="button" className="linkish" onClick={onLogout}>
          退出
        </button>
      </header>

      {!apiConfigured ? (
        <p className="warn">
          管理者設定（APIキー）が未完了のため、現在使用できません。
        </p>
      ) : null}

      <h2 className="sec">入力情報</h2>
      <form onSubmit={onSubmit} className="stack">
        <InputBlock
          title="① 発言ログ（文字起こし）"
          required
          allowPaste
          pastePlaceholder="コピーした会議の文字起こしを貼り付けてください"
          accept=".txt,.docx,text/plain"
          uploadFormats=".txt / .docx"
          mode={transcriptMode}
          text={transcriptText}
          file={transcriptFile}
          onMode={setTranscriptMode}
          onText={setTranscriptText}
          onFile={setTranscriptFile}
        />
        <InputBlock
          title="② 打合せ次第"
          required={false}
          allowPaste
          pastePlaceholder="会議の次第があれば貼り付けてください（なければ空のままでOK）"
          accept=".txt,.docx,.pdf,text/plain,application/pdf"
          uploadFormats=".txt / .docx / .pdf"
          mode={agendaMode}
          text={agendaText}
          file={agendaFile}
          onMode={setAgendaMode}
          onText={setAgendaText}
          onFile={setAgendaFile}
        />
        <InputBlock
          title="③ その他資料"
          required={false}
          allowPaste={false}
          pastePlaceholder=""
          accept=".pdf,.docx,.txt,application/pdf,text/plain"
          uploadFormats=".txt / .docx / .pdf"
          mode="file"
          text=""
          file={materialsFile}
          onMode={() => undefined}
          onText={() => undefined}
          onFile={setMaterialsFile}
        />

        <p className="hint">
          ※ 開催日時・場所・出席者・資料名などは担当者が直接記入してください。
        </p>

        {warnings.map((w) => (
          <p key={w} className="warn">
            {w}
          </p>
        ))}
        {error ? <p className="error">{error}</p> : null}

        <button type="submit" className="cta" disabled={!canSubmit}>
          {loading ? "AIが議事録を作成中…" : "📝 議事録を作成する"}
        </button>
      </form>

      {minutes ? (
        <section className="result">
          {confirms.length > 0 ? (
            <div className="confirm-box">
              <strong>要確認が {confirms.length} 箇所あります。</strong>
              <br />
              Wordファイルダウンロード後に確認してください。
              <details className="details">
                <summary>要確認一覧</summary>
                <ul>
                  {confirms.map((c) => (
                    <li key={c}>
                      <code>{c}</code>
                    </li>
                  ))}
                </ul>
              </details>
            </div>
          ) : (
            <p className="ok">
              要確認タグは検出されませんでした。念のため本文も確認してください。
            </p>
          )}

          <details className="details">
            <summary>議事録内容プレビュー</summary>
            <div className="preview">
              {minutes.議題.map((topic, i) => (
                <div key={`${topic.番号}-${i}`}>
                  <h3>
                    {topic.番号}
                    {topic.見出し}
                  </h3>
                  {topic.小項目.map((sub, j) => (
                    <div key={`${sub.番号}-${j}`} className="sub">
                      <strong>
                        {sub.番号}
                        {sub.見出し}
                      </strong>
                      {sub.説明 ? <p>{sub.説明}</p> : null}
                      {sub.質疑.map((qa, k) => (
                        <div key={k}>
                          <p>
                            - 質問（話者:{qa.話者}）: {qa.質問}
                          </p>
                          <p>
                            - 回答: －
                            {qa.回答.replace(/^[－\-]+/, "")}
                          </p>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ))}
              <p>
                <strong>次回打合せ：</strong>
                {minutes.次回打合せ}
              </p>
              <p>以上</p>
            </div>
          </details>

          <button type="button" className="cta secondary" onClick={downloadDocx}>
            Wordをダウンロード
          </button>
        </section>
      ) : null}
    </div>
  );
}
