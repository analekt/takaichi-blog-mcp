# takaichi-blog-mcp

高市早苗氏（現総理大臣）が公式サイト `sanae.gr.jp` でかつて執筆していたブログ記事（コラム）を [Wayback Machine](https://web.archive.org/) から取得し、LLMに提供する**MCPサーバ**です。記事は公式サイトから削除済みですが、アーカイブには約1,024件が残っています。

## 特徴

- **stdio形式のMCPサーバ**（Claude Desktop等がローカルでサブプロセスとして起動）
- データはユーザーのPC（既定で `~/.takaichi-blog-mcp/`）に**Markdown形式で保管**（生HTMLは保存しません）
- 各記事のYAML frontmatterに**出典URL**（元サイト + Wayback Machine）を記録
- 全文検索・カテゴリ別一覧・本文取得をツールとして公開

## 仕組み（2 コンポーネント）

| コンポーネント | 役割 |
|---|---|
| `takaichi-blog-fetch`（プロビジョニング CLI） | Wayback からの一括ダウンロード（初回に 1 回だけ実行） |
| `takaichi-blog-mcp`（MCP サーバ） | ローカルに保存済みのデータのみを参照（ネットワークアクセスなし） |

一括ダウンロードは約1,024リクエスト（約1.2秒/件 = 約20分）かかるため、**サーバ起動処理には含めていません**（MCPクライアントの初期化タイムアウトを避けるため）。必ず先に `takaichi-blog-fetch` を実行してください。

## インストール

### 必要環境

- Python 3.10以上
- `pip`（または `uv` などのパッケージマネージャ）

### インストール（エンドユーザー向け）

PyPIに公開されているため、リポジトリのクローンは不要です。

```bash
pip install takaichi-blog-mcp
```

これだけで以下2つのコマンドがPATHに登録されます。

- `takaichi-blog-fetch` … ブログ記事の一括ダウンロード（プロビジョニング）
- `takaichi-blog-mcp` … MCPサーバ本体

> **pipx / uv を使う場合（推奨）:** コマンドを隔離環境にインストールできます。
> `pipx install takaichi-blog-mcp` または `uv tool install takaichi-blog-mcp`

### インストールの確認

```bash
takaichi-blog-fetch --help
takaichi-blog-mcp --help
```

### ソースからのインストール（開発者向け）

コードを変更したい場合や開発に参加する場合は、リポジトリをクローンします。

```bash
git clone https://github.com/analekt/takaichi-blog-mcp.git
cd takaichi-blog-mcp
python3 -m venv .venv
source .venv/bin/activate          # Windows は .venv\Scripts\activate
pip install -e ".[dev]"            # 開発依存込みで editable インストール
```

## セットアップ（データのダウンロードと起動）

```bash
# 1. ブログ記事を一括ダウンロード（初回のみ・約20分）
takaichi-blog-fetch
#   --dry-run  対象を確認するだけ（何も書き込まない）
#   --force    既存分も含めて全件再取得

# 2. MCP サーバを起動（通常は MCP クライアントが自動起動するため手動実行は不要）
takaichi-blog-mcp
```

データの保存先は既定で `~/.takaichi-blog-mcp/` です。環境変数`TAKAICHI_BLOG_DATA_DIR` で変更できます。

## Claude Desktop への登録例

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "takaichi-blog": {
      "command": "takaichi-blog-mcp"
    }
  }
}
```

（事前に `takaichi-blog-fetch` を実行してデータをダウンロードしておく必要があります。未ダウンロードの場合、各ツールはダウンロードを促すメッセージを返します）

## 提供する MCP ツール

| ツール | 説明 |
|---|---|
| `takaichi_list_articles` | 記事メタデータの一覧（カテゴリ・公開日で絞り込み、新しい順、ページング対応） |
| `takaichi_list_categories` | カテゴリ一覧（件数・期間付き。各カテゴリは当選期に対応） |
| `takaichi_get_article` | ID を指定して記事本文（Markdown）+ メタデータを取得 |
| `takaichi_search_articles` | タイトル + 本文の全文検索（部分一致・日本語対応、抜粋付き） |

`takaichi_get_article` / `takaichi_search_articles` のレスポンスには`original_url`（元サイト）と`wayback_url`（アーカイブ）が含まれ、LLMがユーザーに出典を提示できます。

## データ形式

各記事はダウンロード後、以下の形式でローカルに保存されます。

`articles/{id}.md`（YAML frontmatter + Markdown）:

```yaml
---
id: 8
title: ようやく臨時国会が召集されました。
category: 5期目だ！野党だ！！永田町通信　平成21年10月～平成24年12月
published_date: 2009-10-26
date_source: html
archived_date: 2025-10-21
original_url: https://www.sanae.gr.jp/column_detail8.html
wayback_url: https://web.archive.org/web/20251021182115/https://www.sanae.gr.jp/column_detail8.html
---

（本文 Markdown）
```

`parsed/{id}.json` には上記メタデータと `content_markdown` がJSONで格納されます（`content_html` は保存しません）。`articles.json` は全記事のメタデータ索引です。

## アーキテクチャ

```
src/takaichi_blog_mcp/
├── config.py     # データディレクトリ・エンドポイント等の定数
├── wayback.py    # CDX API での記事一覧取得 + スナップショット取得（リトライ付き）
├── parser.py     # 取得 HTML → 構造化データ（BeautifulSoup + markdownify）
├── store.py      # ローカル保存/読込（Markdown のみ）
├── search.py     # 一覧・タイトル検索・全文検索（純粋関数、依存なし）
├── fetch.py      # プロビジョニング CLI
└── server.py     # FastMCP サーバ本体（stdio）
```

CDXクエリは `url=sanae.gr.jp/column_detail&matchType=prefix&filter=statuscode:200`で全スナップショットを取得し、`column_detail{id}.html` 形式のURLごとに**最新のスナップショット**を採用します。本文は `…id_/` 形式でWaybackの書き換えを含まない生HTMLを取得しています。

## 開発・テスト

```bash
pip install -e ".[dev]"
pytest                                   # ユニットテスト
pytest --cov=takaichi_blog_mcp           # カバレッジ付き
```

パーサーは参考リポジトリの実HTML（`tests/fixtures/`）に対して検証しており、
ネットワークアクセスなしでオフラインで動作します。

## PyPI への公開（メンテナ向け）

新しいバージョンをPyPIに公開する手順です。

```bash
# 1. バージョンを更新（pyproject.toml の version）

# 2. ビルドツールを用意してパッケージを作成
pip install --upgrade build twine
python -m build                      # dist/ に .whl と .tar.gz を生成

# 3. （任意）TestPyPI で動作確認
twine upload --repository testpypi dist/*

# 4. 本番 PyPI へアップロード
twine upload dist/*
```

> 認証には PyPI の API トークンを使用します
> （`~/.pypirc` もしくは `TWINE_USERNAME=__token__` / `TWINE_PASSWORD=<token>`）。

## ランディングページ（Vercel）

`site/index.html` はプロジェクト紹介用の静的ランディングページ（単一 HTML・依存なし）です。`vercel.json` で公開ディレクトリを `site/` に指定しているため、GitHub リポジトリを Vercel に接続すれば追加設定なしでそのまま配信されます。

```bash
# ローカルで確認
open site/index.html

# Vercel へ（GitHub 連携で push すると自動デプロイ。CLI を使う場合）
npm i -g vercel
vercel            # プレビュー
vercel --prod     # 本番
```

> MCP サーバ本体は stdio 形式でローカル動作するため、Vercel で「動かす」のではなく、あくまで紹介ページのみをホストします。

## 注意

本データはWayback Machineのアーカイブに由来します。著作権は原著者に帰属します。研究・参照目的での利用を想定しており、取得時はWayback Machineに過度な負荷をかけないようレート制限を設けています。
