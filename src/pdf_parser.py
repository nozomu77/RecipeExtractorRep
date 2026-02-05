"""PDF解析・テキスト抽出モジュール"""

import io
from pathlib import Path
from dataclasses import dataclass

import fitz  # PyMuPDF


@dataclass
class PDFContent:
    """PDF内容を保持するデータクラス"""

    filename: str
    total_pages: int
    text_by_page: list[str]
    full_text: str
    metadata: dict


class PDFParser:
    """PDFからテキストを抽出するパーサー"""

    def __init__(self):
        pass

    def parse_file(self, file_path: str) -> PDFContent:
        """
        PDFファイルからテキストを抽出

        Args:
            file_path: PDFファイルのパス

        Returns:
            PDFContent: 抽出された内容
        """
        doc = fitz.open(file_path)
        return self._extract_content(doc, Path(file_path).name)

    def parse_bytes(self, pdf_bytes: bytes, filename: str = "unknown.pdf") -> PDFContent:
        """
        PDFバイナリデータからテキストを抽出

        Args:
            pdf_bytes: PDFのバイナリデータ
            filename: ファイル名（識別用）

        Returns:
            PDFContent: 抽出された内容
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return self._extract_content(doc, filename)

    def _extract_content(self, doc: fitz.Document, filename: str) -> PDFContent:
        """
        PyMuPDFドキュメントからコンテンツを抽出

        Args:
            doc: PyMuPDFドキュメント
            filename: ファイル名

        Returns:
            PDFContent: 抽出された内容
        """
        text_by_page = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            text_by_page.append(text)

        full_text = "\n\n".join(text_by_page)

        metadata = {
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
            "creation_date": doc.metadata.get("creationDate", ""),
        }

        doc.close()

        return PDFContent(
            filename=filename,
            total_pages=len(text_by_page),
            text_by_page=text_by_page,
            full_text=full_text,
            metadata=metadata,
        )

    def parse_multiple_files(self, file_paths: list[str]) -> list[PDFContent]:
        """
        複数のPDFファイルを一括処理

        Args:
            file_paths: PDFファイルパスのリスト

        Returns:
            PDFContentのリスト
        """
        results = []
        for path in file_paths:
            try:
                content = self.parse_file(path)
                results.append(content)
            except Exception as e:
                print(f"[警告] {path} の解析に失敗: {e}")
        return results
