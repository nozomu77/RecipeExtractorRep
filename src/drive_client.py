"""Google Drive連携モジュール（サービスアカウント対応版）"""

import os
import io
import json
import base64
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# Google Drive APIのスコープ（読み取り専用）
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class DriveClient:
    """Google Driveからファイルを取得するクライアント（サービスアカウント対応）"""

    def __init__(
        self,
        service_account_file: Optional[str] = None,
        service_account_base64: Optional[str] = None,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        use_oauth: bool = False,
    ):
        """
        Args:
            service_account_file: サービスアカウントJSONファイルのパス
            service_account_base64: Base64エンコードされたサービスアカウントJSON
            credentials_file: OAuth2用の認証情報ファイル（use_oauth=True時のみ）
            token_file: OAuthトークンの保存先（use_oauth=True時のみ）
            use_oauth: OAuthフロー（ブラウザ認証）を使用するか

        認証の優先順位:
        1. service_account_base64（環境変数向け）
        2. service_account_file（ファイル指定）
        3. 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64
        4. 環境変数 GOOGLE_SERVICE_ACCOUNT_FILE
        5. デフォルトファイル service_account.json
        6. use_oauth=True の場合のみ OAuth認証
        """
        self.service_account_file = service_account_file
        self.service_account_base64 = service_account_base64
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.use_oauth = use_oauth
        self.service = None

    def authenticate(self) -> None:
        """Google Drive APIの認証を行う"""
        creds = None

        # 1. Base64エンコードされたサービスアカウント（引数）
        if self.service_account_base64:
            creds = self._auth_from_base64(self.service_account_base64)

        # 2. サービスアカウントファイル（引数）
        elif self.service_account_file and os.path.exists(self.service_account_file):
            creds = self._auth_from_file(self.service_account_file)

        # 3. 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64
        elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_BASE64"):
            creds = self._auth_from_base64(os.environ["GOOGLE_SERVICE_ACCOUNT_BASE64"])

        # 4. 環境変数 GOOGLE_SERVICE_ACCOUNT_FILE
        elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
            creds = self._auth_from_file(os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])

        # 5. デフォルトファイル service_account.json
        elif os.path.exists("service_account.json"):
            creds = self._auth_from_file("service_account.json")

        # 6. OAuth認証（ローカル用、ブラウザが開く）
        elif self.use_oauth:
            creds = self._auth_oauth()

        else:
            raise FileNotFoundError(
                "認証情報が見つかりません。以下のいずれかを設定してください:\n"
                "  1. 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64（推奨）\n"
                "  2. 環境変数 GOOGLE_SERVICE_ACCOUNT_FILE\n"
                "  3. service_account.json ファイル\n"
                "  4. --use-oauth オプション（ローカル用）"
            )

        self.service = build("drive", "v3", credentials=creds)

    def _auth_from_base64(self, base64_str: str):
        """Base64エンコードされたJSONから認証"""
        json_str = base64.b64decode(base64_str).decode("utf-8")
        service_account_info = json.loads(json_str)
        return service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )

    def _auth_from_file(self, file_path: str):
        """JSONファイルから認証"""
        return service_account.Credentials.from_service_account_file(
            file_path, scopes=SCOPES
        )

    def _auth_oauth(self):
        """OAuth認証（ブラウザが開く）"""
        creds = None

        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

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

            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        return creds

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
            if os.path.exists(output_path):
                base, ext = os.path.splitext(output_path)
                output_path = f"{base}_{pdf_info['id'][:8]}{ext}"

            self.download_pdf(pdf_info["id"], output_path)
            downloaded_paths.append(output_path)

        return downloaded_paths
