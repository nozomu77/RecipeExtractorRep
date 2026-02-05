"""LLMによるレシピ情報抽出モジュール"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

import anthropic

from .pdf_parser import PDFContent


@dataclass
class Recipe:
    """レシピ情報を保持するデータクラス"""

    # 基本情報
    name: str
    description: str = ""

    # カテゴリ・分類
    cuisine_type: str = ""  # 料理ジャンル（フレンチ、和食、中華など）
    meal_type: str = ""  # 食事タイプ（朝食、昼食、夕食、デザートなど）
    dietary_tags: list[str] = field(default_factory=list)  # ハラル、ベジタリアン、グルテンフリーなど

    # 材料
    ingredients: list[dict] = field(default_factory=list)  # [{name, amount, unit}, ...]
    main_ingredients: list[str] = field(default_factory=list)  # 主要食材

    # 調理情報
    servings: str = ""  # 何人分
    prep_time: str = ""  # 下準備時間
    cook_time: str = ""  # 調理時間
    total_time: str = ""  # 合計時間
    difficulty: str = ""  # 難易度

    # 手順
    steps: list[str] = field(default_factory=list)

    # 栄養情報
    calories: str = ""
    nutrition_info: dict = field(default_factory=dict)

    # メタデータ
    source_file: str = ""
    source_page: int = 0
    tips: list[str] = field(default_factory=list)  # コツ・ポイント

    def to_dict(self) -> dict:
        return asdict(self)


EXTRACTION_PROMPT = """以下の料理雑誌記事のテキストから、含まれているすべてのレシピ情報を抽出してください。

## 抽出ルール
- 記事内に複数のレシピがある場合は、すべて抽出してください
- 情報が明示されていない項目はnull（空文字や空リスト）としてください
- 料理ジャンル（cuisine_type）は以下から最も適切なものを選んでください：
  和食, 洋食, フレンチ, イタリアン, 中華, 韓国料理, タイ料理, ベトナム料理,
  インド料理, メキシカン, アメリカン, 地中海料理, 中東料理, アフリカ料理, その他
- 食事制限タグ（dietary_tags）は該当するものをすべて選んでください：
  ハラル, コーシャ, ベジタリアン, ヴィーガン, グルテンフリー, 乳製品不使用,
  ナッツフリー, 低糖質, 低カロリー, 高タンパク

## 出力形式
JSON配列で出力してください。各レシピは以下の構造を持ちます：

```json
[
  {{
    "name": "料理名",
    "description": "料理の説明",
    "cuisine_type": "料理ジャンル",
    "meal_type": "食事タイプ（朝食/昼食/夕食/デザート/軽食など）",
    "dietary_tags": ["該当するタグ"],
    "ingredients": [
      {{"name": "材料名", "amount": "量", "unit": "単位"}}
    ],
    "main_ingredients": ["主要食材1", "主要食材2"],
    "servings": "何人分",
    "prep_time": "下準備時間",
    "cook_time": "調理時間",
    "total_time": "合計時間",
    "difficulty": "難易度（簡単/普通/難しい）",
    "steps": ["手順1", "手順2", "..."],
    "calories": "カロリー",
    "nutrition_info": {{"protein": "...", "fat": "...", "carbs": "..."}},
    "tips": ["コツ1", "コツ2"]
  }}
]
```

## 記事テキスト
{text}

## 注意
- JSON形式のみを出力してください（説明文は不要）
- レシピが見つからない場合は空配列 [] を返してください
"""


class RecipeExtractor:
    """LLMを使ってPDFからレシピを抽出"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Args:
            api_key: Anthropic APIキー
            model: 使用するモデル
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def extract_from_text(
        self, text: str, source_file: str = "", source_page: int = 0
    ) -> list[Recipe]:
        """
        テキストからレシピを抽出

        Args:
            text: 抽出元テキスト
            source_file: ソースファイル名
            source_page: ソースページ番号

        Returns:
            抽出されたレシピのリスト
        """
        # テキストが長すぎる場合は分割処理（Claude APIの制限対応）
        max_chars = 100000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[... テキストが長いため省略 ...]"

        prompt = EXTRACTION_PROMPT.format(text=text)

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # JSON部分を抽出
        recipes_data = self._parse_json_response(response_text)

        # Recipeオブジェクトに変換
        recipes = []
        for data in recipes_data:
            recipe = Recipe(
                name=data.get("name", ""),
                description=data.get("description", ""),
                cuisine_type=data.get("cuisine_type", ""),
                meal_type=data.get("meal_type", ""),
                dietary_tags=data.get("dietary_tags", []),
                ingredients=data.get("ingredients", []),
                main_ingredients=data.get("main_ingredients", []),
                servings=data.get("servings", ""),
                prep_time=data.get("prep_time", ""),
                cook_time=data.get("cook_time", ""),
                total_time=data.get("total_time", ""),
                difficulty=data.get("difficulty", ""),
                steps=data.get("steps", []),
                calories=data.get("calories", ""),
                nutrition_info=data.get("nutrition_info", {}),
                tips=data.get("tips", []),
                source_file=source_file,
                source_page=source_page,
            )
            recipes.append(recipe)

        return recipes

    def extract_from_pdf_content(self, pdf_content: PDFContent) -> list[Recipe]:
        """
        PDFContentからレシピを抽出

        Args:
            pdf_content: 解析済みPDFコンテンツ

        Returns:
            抽出されたレシピのリスト
        """
        all_recipes = []

        # ページごとに処理（または全体を一括処理）
        # 全体テキストで処理する場合
        recipes = self.extract_from_text(
            pdf_content.full_text, source_file=pdf_content.filename
        )
        all_recipes.extend(recipes)

        return all_recipes

    def _parse_json_response(self, response: str) -> list[dict]:
        """
        LLMレスポンスからJSONを抽出

        Args:
            response: LLMからのレスポンステキスト

        Returns:
            パースされたJSONデータ（レシピのリスト）
        """
        import re

        json_str = None

        # 方法1: ```json ... ``` ブロックを探す
        json_block_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if json_block_match:
            json_str = json_block_match.group(1).strip()

        # 方法2: ``` ... ``` ブロックを探す
        if not json_str:
            code_block_match = re.search(r'```\s*([\s\S]*?)\s*```', response)
            if code_block_match:
                json_str = code_block_match.group(1).strip()

        # 方法3: [ ... ] 配列を直接探す
        if not json_str:
            array_match = re.search(r'(\[[\s\S]*\])', response)
            if array_match:
                json_str = array_match.group(1).strip()

        # 方法4: そのまま試す
        if not json_str:
            json_str = response.strip()

        # パース試行
        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            return []
        except json.JSONDecodeError as e:
            print(f"[警告] JSON解析に失敗しました: {e}")
            # デバッグ用: 最初の200文字を表示
            print(f"[デバッグ] レスポンス先頭: {response[:200]}...")
            return []
