"""Google Drive連携モジュール"""

import os
import io
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# Google Drive APIのスコープ（読み取り専用）
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveClient:
    """Google Driveからファイルを取得するクライアント"""

    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
    ):
        """
        Args:
            credentials_file: OAuth2クライアントIDの認証情報ファイル
            token_file: 認証トークンの保存先
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None

    def authenticate(self) -> None:
        """Google Drive APIの認証を行う"""
        creds = None

        # 既存のトークンを読み込む
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        # トークンがない、または期限切れの場合は再認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"認証情報ファイルが見つかりません: {self.credentials_file}\n"
                        "Google Cloud Consoleからダウンロードしてください。"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # トークンを保存
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        self.service = build("drive", "v3", credentials=creds)

    def list_pdfs_in_folder(
        self, folder_id: str, recursive: bool = True
    ) -> list[dict]:
        """
        指定フォルダ内のPDFファイル一覧を取得

        Args:
            folder_id: Google DriveのフォルダID
            recursive: サブフォルダも検索するか

        Returns:
            PDFファイル情報のリスト [{id, name, mimeType, modifiedTime}, ...]
        """
        if not self.service:
            self.authenticate()

        pdf_files = []
        folders_to_search = [folder_id]

        while folders_to_search:
            current_folder = folders_to_search.pop(0)

            # フォルダ内のファイルを取得
            query = f"'{current_folder}' in parents and trashed = false"
            results = (
                self.service.files()
                .list(
                    q=query,
                    fields="files(id, name, mimeType, modifiedTime)",
                    pageSize=1000,
                )
                .execute()
            )

            for item in results.get("files", []):
                if item["mimeType"] == "application/pdf":
                    pdf_files.append(item)
                elif (
                    recursive
                    and item["mimeType"] == "application/vnd.google-apps.folder"
                ):
                    folders_to_search.append(item["id"])

        return pdf_files

    def download_pdf(
        self, file_id: str, output_path: Optional[str] = None
    ) -> bytes:
        """
        PDFファイルをダウンロード

        Args:
            file_id: ファイルID
            output_path: 保存先パス（指定時はファイルに保存）

        Returns:
            PDFのバイナリデータ
        """
        if not self.service:
            self.authenticate()

        request = self.service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        pdf_bytes = buffer.getvalue()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)

        return pdf_bytes

    def download_all_pdfs(
        self, folder_id: str, output_dir: str, recursive: bool = True
    ) -> list[str]:
        """
        フォルダ内の全PDFをダウンロード

        Args:
            folder_id: Google DriveのフォルダID
            output_dir: 保存先ディレクトリ
            recursive: サブフォルダも含めるか

        Returns:
            ダウンロードしたファイルパスのリスト
        """
        pdf_files = self.list_pdfs_in_folder(folder_id, recursive)
        downloaded_paths = []

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        for pdf_info in pdf_files:
            output_path = os.path.join(output_dir, pdf_info["name"])
            # 同名ファイルがある場合はIDを付加
            if os.path.exists(output_path):
                base, ext = os.path.splitext(output_path)
                output_path = f"{base}_{pdf_info['id'][:8]}{ext}"

            self.download_pdf(pdf_info["id"], output_path)
            downloaded_paths.append(output_path)

        return downloaded_paths
