"""データ保存・フィルタリングモジュール"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import asdict

from .recipe_extractor import Recipe


class RecipeStorage:
    """レシピデータの保存・読み込み・フィルタリングを行う"""

    def __init__(self, storage_path: str = "./data/recipes.json"):
        """
        Args:
            storage_path: レシピデータの保存先パス
        """
        self.storage_path = Path(storage_path)
        self.recipes: list[Recipe] = []
        self._load()

    def _load(self) -> None:
        """保存済みデータを読み込む"""
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.recipes = [self._dict_to_recipe(r) for r in data]

    def _save(self) -> None:
        """データを保存する"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in self.recipes],
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _dict_to_recipe(self, data: dict) -> Recipe:
        """辞書からRecipeオブジェクトを作成"""
        return Recipe(
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
            source_file=data.get("source_file", ""),
            source_page=data.get("source_page", 0),
        )

    def add_recipes(self, recipes: list[Recipe]) -> int:
        """
        レシピを追加

        Args:
            recipes: 追加するレシピのリスト

        Returns:
            追加されたレシピ数
        """
        # 重複チェック（名前とソースファイルで判断）
        existing = {(r.name, r.source_file) for r in self.recipes}
        new_recipes = [
            r for r in recipes if (r.name, r.source_file) not in existing
        ]
        self.recipes.extend(new_recipes)
        self._save()
        return len(new_recipes)

    def get_all(self) -> list[Recipe]:
        """全レシピを取得"""
        return self.recipes.copy()

    def filter(
        self,
        cuisine_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        dietary_tags: Optional[list[str]] = None,
        ingredient: Optional[str] = None,
        difficulty: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> list[Recipe]:
        """
        条件でレシピを絞り込み

        Args:
            cuisine_type: 料理ジャンル（フレンチ、和食など）
            meal_type: 食事タイプ（朝食、昼食など）
            dietary_tags: 食事制限タグ（ハラル、ベジタリアンなど）- AND条件
            ingredient: 含む材料（部分一致）
            difficulty: 難易度
            keyword: キーワード検索（名前・説明から）

        Returns:
            条件に合致するレシピのリスト
        """
        results = self.recipes.copy()

        if cuisine_type:
            results = [
                r for r in results
                if cuisine_type.lower() in r.cuisine_type.lower()
            ]

        if meal_type:
            results = [
                r for r in results
                if meal_type.lower() in r.meal_type.lower()
            ]

        if dietary_tags:
            # すべてのタグを含むものを抽出（AND条件）
            for tag in dietary_tags:
                results = [
                    r for r in results
                    if any(tag.lower() in t.lower() for t in r.dietary_tags)
                ]

        if ingredient:
            results = [
                r for r in results
                if any(
                    ingredient.lower() in ing.get("name", "").lower()
                    for ing in r.ingredients
                )
                or any(ingredient.lower() in mi.lower() for mi in r.main_ingredients)
            ]

        if difficulty:
            results = [
                r for r in results
                if difficulty.lower() in r.difficulty.lower()
            ]

        if keyword:
            keyword_lower = keyword.lower()
            results = [
                r for r in results
                if keyword_lower in r.name.lower()
                or keyword_lower in r.description.lower()
            ]

        return results

    def get_cuisine_types(self) -> list[str]:
        """登録されている料理ジャンル一覧を取得"""
        types = set()
        for r in self.recipes:
            if r.cuisine_type:
                types.add(r.cuisine_type)
        return sorted(types)

    def get_dietary_tags(self) -> list[str]:
        """登録されている食事制限タグ一覧を取得"""
        tags = set()
        for r in self.recipes:
            tags.update(r.dietary_tags)
        return sorted(tags)

    def get_statistics(self) -> dict:
        """統計情報を取得"""
        cuisine_counts = {}
        tag_counts = {}

        for r in self.recipes:
            # ジャンル別カウント
            ct = r.cuisine_type or "不明"
            cuisine_counts[ct] = cuisine_counts.get(ct, 0) + 1

            # タグ別カウント
            for tag in r.dietary_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return {
            "total_recipes": len(self.recipes),
            "cuisine_counts": cuisine_counts,
            "dietary_tag_counts": tag_counts,
            "source_files": len(set(r.source_file for r in self.recipes)),
        }

    def export_csv(self, output_path: str) -> None:
        """CSV形式でエクスポート"""
        import csv

        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # ヘッダー
            writer.writerow([
                "料理名", "説明", "ジャンル", "食事タイプ", "食事制限",
                "人数", "調理時間", "難易度", "カロリー", "ソースファイル"
            ])
            # データ
            for r in self.recipes:
                writer.writerow([
                    r.name,
                    r.description,
                    r.cuisine_type,
                    r.meal_type,
                    ", ".join(r.dietary_tags),
                    r.servings,
                    r.total_time,
                    r.difficulty,
                    r.calories,
                    r.source_file,
                ])

    def clear(self) -> None:
        """全データを削除"""
        self.recipes = []
        self._save()
