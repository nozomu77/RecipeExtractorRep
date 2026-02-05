#!/usr/bin/env python3
"""Recipe Extractor CLI - 料理雑誌PDFからレシピを抽出・検索するツール"""

import os
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

from src.drive_client import DriveClient
from src.pdf_parser import PDFParser
from src.recipe_extractor import RecipeExtractor
from src.storage import RecipeStorage

# .envファイルから環境変数を読み込む
load_dotenv()

console = Console()


def load_config(config_path: str = "config.json") -> dict:
    """設定ファイルを読み込む"""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@click.group()
@click.option("--config", default="config.json", help="設定ファイルのパス")
@click.pass_context
def cli(ctx, config):
    """🍳 Recipe Extractor - 料理雑誌PDFからレシピを抽出"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.option("--folder-id", "-f", required=True, help="Google DriveのフォルダID")
@click.option("--output-dir", "-o", default="./data/pdfs", help="PDF保存先ディレクトリ")
@click.option("--use-oauth", is_flag=True, help="OAuth認証を使用（ローカル用、ブラウザが開く）")
@click.pass_context
def download(ctx, folder_id, output_dir, use_oauth):
    """Google DriveからPDFをダウンロード

    認証方法（優先順位）:
    1. 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64（Codespaces推奨）
    2. 環境変数 GOOGLE_SERVICE_ACCOUNT_FILE
    3. service_account.json ファイル
    4. --use-oauth オプション（ローカル用）
    """
    config = ctx.obj["config"]
    drive_config = config.get("google_drive", {})

    console.print("[bold blue]Google Driveからダウンロード中...[/]")

    # 認証方法を表示
    if os.environ.get("GOOGLE_SERVICE_ACCOUNT_BASE64"):
        console.print("[dim]認証: 環境変数 GOOGLE_SERVICE_ACCOUNT_BASE64[/]")
    elif os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
        console.print(f"[dim]認証: 環境変数 GOOGLE_SERVICE_ACCOUNT_FILE[/]")
    elif os.path.exists("service_account.json"):
        console.print("[dim]認証: service_account.json[/]")
    elif use_oauth:
        console.print("[dim]認証: OAuth（ブラウザ認証）[/]")

    try:
        client = DriveClient(
            service_account_file=drive_config.get("service_account_file"),
            credentials_file=drive_config.get("credentials_file", "credentials.json"),
            token_file=drive_config.get("token_file", "token.json"),
            use_oauth=use_oauth,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("PDFファイルを検索・ダウンロード中...", total=None)
            downloaded = client.download_all_pdfs(folder_id, output_dir)

        console.print(f"[green]✓ {len(downloaded)}件のPDFをダウンロードしました[/]")
        for path in downloaded:
            console.print(f"  - {path}")

    except FileNotFoundError as e:
        console.print(f"[red]エラー: {e}[/]")
        raise click.Abort()


@cli.command()
@click.option("--input-dir", "-i", default="./data/pdfs", help="PDFディレクトリ")
@click.option("--file", "-f", multiple=True, help="処理するPDFファイル（複数指定可）")
@click.pass_context
def extract(ctx, input_dir, file):
    """PDFからレシピを抽出"""
    config = ctx.obj["config"]
    api_key = config.get("anthropic", {}).get("api_key") or os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        console.print("[red]エラー: ANTHROPIC_API_KEYが設定されていません[/]")
        console.print("config.jsonまたは環境変数で設定してください")
        raise click.Abort()

    # 処理対象ファイルを取得
    pdf_files = []
    if file:
        pdf_files = list(file)
    else:
        input_path = Path(input_dir)
        if input_path.exists():
            pdf_files = [str(p) for p in input_path.glob("*.pdf")]

    if not pdf_files:
        console.print("[yellow]処理対象のPDFファイルが見つかりません[/]")
        return

    console.print(f"[bold blue]{len(pdf_files)}件のPDFを処理します...[/]")

    parser = PDFParser()
    extractor = RecipeExtractor(api_key)
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    total_recipes = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for pdf_path in pdf_files:
            task = progress.add_task(f"処理中: {Path(pdf_path).name}", total=None)

            try:
                # PDF解析
                pdf_content = parser.parse_file(pdf_path)
                console.print(f"  [dim]→ {pdf_content.total_pages}ページを解析[/]")

                # レシピ抽出
                recipes = extractor.extract_from_pdf_content(pdf_content)
                console.print(f"  [dim]→ {len(recipes)}件のレシピを検出[/]")

                # 保存
                added = storage.add_recipes(recipes)
                total_recipes += added

                if added > 0:
                    console.print(f"  [green]✓ {added}件を保存[/]")
                else:
                    console.print(f"  [yellow]- 新規レシピなし（重複）[/]")

            except Exception as e:
                console.print(f"  [red]✗ エラー: {e}[/]")

            progress.remove_task(task)

    console.print(f"\n[bold green]完了: 合計{total_recipes}件のレシピを追加しました[/]")


@cli.command()
@click.option("--cuisine", "-c", help="料理ジャンル（フレンチ、和食など）")
@click.option("--dietary", "-d", multiple=True, help="食事制限タグ（ハラル、ベジタリアンなど）")
@click.option("--ingredient", "-i", help="含む材料")
@click.option("--keyword", "-k", help="キーワード検索")
@click.option("--difficulty", help="難易度（簡単、普通、難しい）")
@click.option("--limit", "-l", default=20, help="表示件数")
@click.pass_context
def search(ctx, cuisine, dietary, ingredient, keyword, difficulty, limit):
    """レシピを検索・フィルタリング"""
    config = ctx.obj["config"]
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    # フィルタリング
    results = storage.filter(
        cuisine_type=cuisine,
        dietary_tags=list(dietary) if dietary else None,
        ingredient=ingredient,
        keyword=keyword,
        difficulty=difficulty,
    )

    if not results:
        console.print("[yellow]条件に合うレシピが見つかりませんでした[/]")
        return

    console.print(f"[bold blue]{len(results)}件のレシピが見つかりました[/]\n")

    # テーブル表示
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("料理名", style="cyan", width=25)
    table.add_column("ジャンル", width=12)
    table.add_column("食事制限", width=20)
    table.add_column("難易度", width=8)
    table.add_column("時間", width=10)

    for recipe in results[:limit]:
        table.add_row(
            recipe.name[:24] + "..." if len(recipe.name) > 24 else recipe.name,
            recipe.cuisine_type or "-",
            ", ".join(recipe.dietary_tags[:2]) or "-",
            recipe.difficulty or "-",
            recipe.total_time or "-",
        )

    console.print(table)

    if len(results) > limit:
        console.print(f"\n[dim]...他 {len(results) - limit}件[/]")


@cli.command()
@click.argument("name")
@click.pass_context
def show(ctx, name):
    """レシピの詳細を表示"""
    config = ctx.obj["config"]
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    results = storage.filter(keyword=name)

    if not results:
        console.print(f"[yellow]'{name}'に一致するレシピが見つかりません[/]")
        return

    recipe = results[0]

    # 詳細表示
    panel_content = f"""
[bold cyan]{recipe.name}[/]
{recipe.description}

[bold]ジャンル:[/] {recipe.cuisine_type or '不明'}
[bold]食事タイプ:[/] {recipe.meal_type or '不明'}
[bold]食事制限:[/] {', '.join(recipe.dietary_tags) or 'なし'}
[bold]難易度:[/] {recipe.difficulty or '不明'}
[bold]人数:[/] {recipe.servings or '不明'}
[bold]調理時間:[/] {recipe.total_time or '不明'}
[bold]カロリー:[/] {recipe.calories or '不明'}

[bold yellow]材料:[/]
"""
    for ing in recipe.ingredients:
        panel_content += f"  • {ing.get('name', '')} {ing.get('amount', '')} {ing.get('unit', '')}\n"

    panel_content += "\n[bold yellow]手順:[/]\n"
    for i, step in enumerate(recipe.steps, 1):
        panel_content += f"  {i}. {step}\n"

    if recipe.tips:
        panel_content += "\n[bold yellow]コツ・ポイント:[/]\n"
        for tip in recipe.tips:
            panel_content += f"  💡 {tip}\n"

    console.print(Panel(panel_content, title="レシピ詳細", border_style="green"))


@cli.command()
@click.pass_context
def stats(ctx):
    """統計情報を表示"""
    config = ctx.obj["config"]
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    statistics = storage.get_statistics()

    console.print(Panel(
        f"""
[bold cyan]レシピ総数:[/] {statistics['total_recipes']}件
[bold cyan]ソースファイル数:[/] {statistics['source_files']}件

[bold yellow]ジャンル別:[/]
""" + "\n".join(f"  • {k}: {v}件" for k, v in sorted(statistics['cuisine_counts'].items(), key=lambda x: -x[1])) + """

[bold yellow]食事制限タグ別:[/]
""" + "\n".join(f"  • {k}: {v}件" for k, v in sorted(statistics['dietary_tag_counts'].items(), key=lambda x: -x[1])),
        title="統計情報",
        border_style="blue"
    ))


@cli.command()
@click.pass_context
def categories(ctx):
    """利用可能なカテゴリ一覧を表示"""
    config = ctx.obj["config"]
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    cuisine_types = storage.get_cuisine_types()
    dietary_tags = storage.get_dietary_tags()

    console.print("[bold cyan]料理ジャンル:[/]")
    for ct in cuisine_types:
        console.print(f"  • {ct}")

    console.print("\n[bold cyan]食事制限タグ:[/]")
    for tag in dietary_tags:
        console.print(f"  • {tag}")


@cli.command()
@click.option("--output", "-o", default="./data/recipes.csv", help="出力ファイルパス")
@click.pass_context
def export(ctx, output):
    """レシピをCSV形式でエクスポート"""
    config = ctx.obj["config"]
    storage_path = config.get("storage", {}).get("recipes_file", "./data/recipes.json")
    storage = RecipeStorage(storage_path)

    storage.export_csv(output)
    console.print(f"[green]✓ {output} にエクスポートしました[/]")


if __name__ == "__main__":
    cli()
