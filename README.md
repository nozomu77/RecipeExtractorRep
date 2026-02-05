# Recipe Extractor

料理雑誌のPDFからレシピ情報を自動抽出し、カテゴリで検索・フィルタリングできるCLIツール。

## 機能

- **Google Drive連携**: 指定フォルダ内のPDFを自動ダウンロード
- **PDF解析**: テキスト抽出（PyMuPDF使用）
- **AI抽出**: Claude APIでレシピ情報を構造化抽出
- **フィルタリング**: 料理ジャンル、食事制限（ハラル等）、材料などで絞り込み
- **エクスポート**: CSV形式で出力可能

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Google Drive API設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. Google Drive APIを有効化
3. OAuth 2.0クライアントIDを作成（デスクトップアプリ）
4. `credentials.json` をダウンロードしてプロジェクトルートに配置

### 3. Anthropic API設定

以下のいずれかの方法でAPIキーを設定:

**方法A: 環境変数**
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

**方法B: .envファイル**
```bash
echo 'ANTHROPIC_API_KEY=your-api-key' > .env
```

**方法C: config.json**
```bash
cp config.example.json config.json
# config.jsonを編集してAPIキーを設定
```

## 使い方

### PDFをGoogle Driveからダウンロード

```bash
# フォルダIDは Google Drive URLから取得
# 例: https://drive.google.com/drive/folders/XXXXX の XXXXX 部分
python main.py download -f YOUR_FOLDER_ID
```

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

### レシピ詳細を表示

```bash
python main.py show "チキンカレー"
```

### 統計情報・カテゴリ一覧

```bash
# 統計情報
python main.py stats

# 利用可能なカテゴリ一覧
python main.py categories
```

### CSVエクスポート

```bash
python main.py export -o recipes.csv
```

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

## ディレクトリ構成

```
.
├── main.py              # CLIエントリーポイント
├── src/
│   ├── drive_client.py  # Google Drive連携
│   ├── pdf_parser.py    # PDF解析
│   ├── recipe_extractor.py  # LLMレシピ抽出
│   └── storage.py       # データ保存・フィルタリング
├── data/
│   ├── pdfs/            # ダウンロードしたPDF
│   └── recipes.json     # 抽出したレシピデータ
├── config.json          # 設定ファイル
├── credentials.json     # Google OAuth認証情報
└── requirements.txt
```

## ライセンス

MIT License
