"""
PDF・テキストファイルからテキストを抽出するモジュール。
"""

import io
from pathlib import Path
from typing import Union

import pdfplumber


def extract_text_from_pdf(file: Union[str, Path, bytes, io.BytesIO]) -> str:
    """
    PDFからテキストを抽出する。

    Args:
        file: ファイルパス、バイト列、またはBytesIOオブジェクト

    Returns:
        抽出されたテキスト（ページ間は改行で結合）
    """
    if isinstance(file, (str, Path)):
        with pdfplumber.open(file) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    else:
        if isinstance(file, bytes):
            file = io.BytesIO(file)
        with pdfplumber.open(file) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]

    return "\n".join(pages).strip()


def extract_text_from_txt(file: Union[str, Path, bytes]) -> str:
    """
    テキストファイルの内容を返す。

    Args:
        file: ファイルパス、またはバイト列

    Returns:
        テキスト内容
    """
    if isinstance(file, bytes):
        # UTF-8で試み、失敗したらShift-JISで再試行
        for encoding in ("utf-8", "utf-8-sig", "shift-jis", "cp932"):
            try:
                return file.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file.decode("utf-8", errors="replace")

    path = Path(file)
    for encoding in ("utf-8", "utf-8-sig", "shift-jis", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    # POC②: サンプルPDF確認用
    import sys
    if len(sys.argv) < 2:
        print("使用方法: python extractor.py <PDFファイルパス>")
        sys.exit(1)

    path = sys.argv[1]
    text = extract_text_from_pdf(path)
    print("=== 抽出テキスト ===")
    print(text[:2000])
    print(f"\n... 合計 {len(text)} 文字")
