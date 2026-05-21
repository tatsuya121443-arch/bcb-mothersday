# 楽天商品データ AI エンリッチメント PoC

楽天市場の商品データに、楽天AIエージェントが自然言語クエリ
（例:「義母への母の日 5000円以下」）から推薦しやすい強化フィールドを
Claude API で自動生成するスクリプトです。

## 何が出来るか

入力（RMSのCSVエクスポート）に対し、以下を生成して列追加します。

| フィールド | 内容 |
|---|---|
| `long_description` | 300–500字の情景・触感込み紹介文 |
| `use_case_tags` | 用途タグ（母の日 / 誕生日 / 結婚祝い 等） |
| `persona_tags` | 想定ターゲット（40代女性 / 義母 等） |
| `occasion_copies` | シーン別キャッチコピー |
| `faqs` | よくある質問 5件 |
| `ai_keywords` | AIエージェントが拾いやすい自然言語クエリ語 |
| `styling_tips` | コーデ・使い方提案 |

優先度ロジック: `在庫あり × 売上ランキング上位 × レビュー数多` の順に処理。
欠品は自動スキップ。

## セットアップ

```bash
# 1. このリポジトリを clone
git clone https://github.com/tatsuya121443-arch/bcb-mothersday.git
cd bcb-mothersday

# 2. 依存パッケージをインストール
pip install -r scripts/requirements.txt

# 3. Anthropic APIキーを設定（https://console.anthropic.com/ で発行）
export ANTHROPIC_API_KEY=sk-ant-xxxxx
```

## 実行

```bash
# サンプル入力（1商品）で試す
python3 scripts/bcb_ai_enrich.py \
    --input scripts/sample_input.csv \
    --output scripts/sample_output.csv \
    --limit 1

# 本番: RMSからエクスポートしたCSVを差し替え
python3 scripts/bcb_ai_enrich.py \
    --input ~/Downloads/rms_export.csv \
    --output enriched.csv
```

出力CSVには元の列＋上記7つの強化列が並びます。
リスト/オブジェクト型のフィールドはJSON文字列として書き込まれます。

## 入力CSVのカラム

`scripts/sample_input.csv` を参照。最低限必要なカラム:

```
商品管理番号, 商品名, カテゴリ, 価格, 在庫数, ブランド,
素材, サイズ, バリエーション, 商品説明,
レビュー数, 平均評価, 売上ランキング
```

RMSエクスポートのカラム名と完全一致していない場合は
`scripts/bcb_ai_enrich.py` の `row.get('...')` を編集してください。

## モデル選択とコスト目安

`scripts/bcb_ai_enrich.py` 冒頭の `MODEL` を変更可能。

| モデル | 1商品あたり | 100商品 | 用途 |
|---|---|---|---|
| `claude-haiku-4-5` | 約 0.5円 | 約 50円 | 大量バッチ |
| `claude-sonnet-4-6`（デフォルト）| 約 3円 | 約 300円 | バランス |
| `claude-opus-4-7` | 約 15円 | 約 1500円 | 高品質仕上げ |

※ 実価格は[公式料金表](https://www.anthropic.com/pricing)で確認。
システムプロンプトはプロンプトキャッシュ済みなので、
連続実行ほど安くなります。

## 重要な原則（プロンプトに組み込み済み）

- 入力にない仕様（素材・原産国など）は推測しない
- 薬機法・景表法に抵触する誇大表現を禁止
- ペルソナと用途を具体化（「女性向け」より「義母への母の日」）

## 想定ワークフロー

1. RMS から対象カテゴリの商品CSVをエクスポート
2. 本スクリプトで強化フィールドを生成
3. 出力CSVを目視レビュー（特に `long_description` と `faqs`）
4. RMS の商品説明欄・タグ欄に反映
   （`occasion_copies` はLP用、`ai_keywords` はメタタグ用 等）

## 次の改善余地

- 商品画像URLを `vision` で読み込み、色・柄・素材感を自動抽出
- 楽天検索ログから「実際の自然言語クエリ」を逆引きしてプロンプト改善
- 在庫切れ商品の `use_case_tags` だけ流用して「代替品レコメンド」生成
