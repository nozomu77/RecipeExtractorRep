# Recipe Extractor

料理雑誌のPDFからレシピ情報を自動抽出し、カテゴリで検索・フィルタリングできるCLIツール。

## 機能

- **Google Drive連携**: 指定フォルダ内のPDFを自動ダウンロード
- **PDF解析**: テキスト抽出（PyMuPDF使用）
- **AI抽出**: Claude APIでレシピ情報を構造化抽出
- **フィルタリング**: 料理ジャンル、食事制限（ハラル等）、材料などで絞り込み
- **エクスポート**: CSV形式で出力可能

---

## セットアップ

### 環境別ガイド

| 環境 | 推奨認証方式 | 設定の難易度 |
|------|-------------|-------------|
| **GitHub Codespaces** | サービスアカウント + GitHub Secrets | ★★☆ |
| **ローカルPC** | OAuth認証（ブラウザ） | ★☆☆ |

---

## Codespaces でのセットアップ（推奨）

### Step 1: 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### Step 2: Google Cloud サービスアカウント作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを作成（または既存のを選択）
3. 「APIとサービス」→「ライブラリ」→「Google Drive API」を有効化
4. 「IAMと管理」→「サービスアカウント」→「+ サービスアカウントを作成」
5. 名前を入力（例: `recipe-extractor`）→「作成して続行」→「完了」
6. 作成したサービスアカウントをクリック
7. 「キー」タブ →「鍵を追加」→「新しい鍵を作成」→「JSON」→「作成」
8. JSONファイルがダウンロードされる

### Step 3: Google Driveフォルダをサービスアカウントと共有

1. ダウンロードしたJSONファイルを開き、`client_email` の値をコピー
   ```
   例: recipe-extractor@project-id.iam.gserviceaccount.com
   ```
2. Google Driveで対象フォルダを右クリック →「共有」
3. コピーしたメールアドレスを追加（閲覧者権限でOK）
4. 「送信」をクリック

### Step 4: GitHub Secrets に登録

**サービスアカウントJSONをBase64エンコード:**

```bash
# ローカルPCで実行
cat path/to/service-account.json | base64 -w 0
# → 出力された文字列をコピー
```

**GitHub Secrets に追加:**

1. リポジトリの「Settings」→「Secrets and variables」→「Codespaces」
2. 「New repository secret」で以下を追加:

| Name | Value |
|------|-------|
| `GOOGLE_SERVICE_ACCOUNT_BASE64` | （Base64文字列） |
| `ANTHROPIC_API_KEY` | `sk-ant-xxxxxxxx` |

3. **Codespacesを再起動**（Secretsを反映するため）

### Step 5: 実行

```bash
# PDFをダウンロード
python main.py download -f YOUR_FOLDER_ID

# レシピを抽出
python main.py extract

# 検索
python main.py search --cuisine フレンチ
```

---

## ローカルPC でのセットアップ

### Step 1: 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### Step 2: Google Drive API設定（OAuth）

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」→「Google Drive API」を有効化
3. 「APIとサービス」→「OAuth同意画面」を設定
   - 「外部」を選択
   - アプリ名、メールアドレスを入力
   - テストユーザーに自分のメールを追加
4. 「APIとサービス」→「認証情報」→「+ 認証情報を作成」→「OAuthクライアントID」
   - アプリケーションの種類: **デスクトップアプリ**
5. 「JSONをダウンロード」→ `credentials.json` としてプロジェクトルートに配置

### Step 3: Anthropic API設定

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxx"
# または
echo 'ANTHROPIC_API_KEY=sk-ant-xxxxxxxx' > .env
```

### Step 4: 実行

```bash
# PDFをダウンロード（初回はブラウザが開く）
python main.py download -f YOUR_FOLDER_ID --use-oauth

# レシピを抽出
python main.py extract

# 検索
python main.py search --cuisine フレンチ
```

---

## 使い方

### PDFをGoogle Driveからダウンロード

```bash
# Codespaces（サービスアカウント認証）
python main.py download -f YOUR_FOLDER_ID

# ローカル（OAuth認証）
python main.py download -f YOUR_FOLDER_ID --use-oauth
```

**フォルダIDの取得方法:**
Google Drive URLの `https://drive.google.com/drive/folders/XXXXX` の `XXXXX` 部分

### PDFからレシピを抽出

```bash
# ディレクトリ内の全PDFを処理
python main.py extract

# 特定のファイルを処理
python main.py extract -f recipe1.pdf -f recipe2.pdf
```

### レシピを検索

```bash
# 全レシピ表示
python main.py search

# 料理ジャンルで絞り込み
python main.py search --cuisine フレンチ
python main.py search -c 和食

# 食事制限で絞り込み
python main.py search --dietary ハラル
python main.py search -d ベジタリアン -d グルテンフリー

# 材料で絞り込み
python main.py search --ingredient 鶏肉

# キーワード検索
python main.py search --keyword カレー

# 複合検索
python main.py search -c イタリアン -d ベジタリアン -k パスタ
```

### その他のコマンド

```bash
# レシピ詳細を表示
python main.py show "チキンカレー"

# 統計情報
python main.py stats

# 利用可能なカテゴリ一覧
python main.py categories

# CSVエクスポート
python main.py export -o recipes.csv
```

---

## 認証方法の優先順位

| 優先度 | 方法 | 環境 |
|--------|------|------|
| 1 | 環境変数 `GOOGLE_SERVICE_ACCOUNT_BASE64` | Codespaces推奨 |
| 2 | 環境変数 `GOOGLE_SERVICE_ACCOUNT_FILE` | サーバー環境 |
| 3 | `service_account.json` ファイル | ローカル/サーバー |
| 4 | `--use-oauth` オプション | ローカルPC |

---

## 抽出される情報

| 項目 | 説明 |
|------|------|
| name | 料理名 |
| description | 説明 |
| cuisine_type | 料理ジャンル（和食、フレンチ、中華など） |
| meal_type | 食事タイプ（朝食、昼食、夕食、デザートなど） |
| dietary_tags | 食事制限タグ（ハラル、ベジタリアン、グルテンフリーなど） |
| ingredients | 材料リスト（名前、量、単位） |
| main_ingredients | 主要食材 |
| servings | 何人分 |
| prep_time | 下準備時間 |
| cook_time | 調理時間 |
| total_time | 合計時間 |
| difficulty | 難易度 |
| steps | 調理手順 |
| calories | カロリー |
| nutrition_info | 栄養情報 |
| tips | コツ・ポイント |

---

## ディレクトリ構成

```
.
├── main.py              # CLIエントリーポイント
├── src/
│   ├── drive_client.py  # Google Drive連携（サービスアカウント対応）
│   ├── pdf_parser.py    # PDF解析
│   ├── recipe_extractor.py  # LLMレシピ抽出
│   └── storage.py       # データ保存・フィルタリング
├── data/
│   ├── pdfs/            # ダウンロードしたPDF
│   └── recipes.json     # 抽出したレシピデータ
├── config.json          # 設定ファイル（オプション）
└── requirements.txt
```

---

## トラブルシューティング

### 「認証情報が見つかりません」エラー

```
認証情報が見つかりません。以下のいずれかを設定してください:
  1. 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64（推奨）
  ...
```

→ GitHub Secretsが正しく設定されているか確認し、Codespacesを再起動

### 「The caller does not have permission」エラー

→ Google Driveフォルダがサービスアカウントと共有されているか確認

### Codespaces再起動後にSecretsが反映されない

→ Codespacesを完全に停止（Stop）してから再度開始

---

## ライセンス

MIT License
