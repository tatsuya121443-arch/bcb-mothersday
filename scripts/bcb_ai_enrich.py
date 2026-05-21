#!/usr/bin/env python3
"""
楽天RMS商品CSVを Claude API で AI エージェント向けに強化するPoC。

入力: RMSエクスポート風CSV
出力: 用途タグ・ペルソナ・FAQ等を追加したCSV
優先度: 在庫あり × 売れ筋ランキング × レビュー数

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python3 scripts/bcb_ai_enrich.py \
      --input sample_input.csv \
      --output sample_output.csv \
      --limit 1
"""

import argparse
import csv
import json
import os
import sys

import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """あなたは楽天市場の店舗運営を支援する商品データエンリッチメントAIです。
入力された商品情報を読み取り、楽天AIエージェントが「ユーザーの自然言語クエリ」から
推薦しやすいよう、構造化された強化フィールドをJSONで返してください。

# 重要原則
- 入力にない仕様（素材、サイズ、原産国など）は推測で書かない。不明なら空文字にする
- 誇大表現を避ける（薬機法・景表法に抵触する表現禁止）
- ペルソナと用途は具体的に（「女性向け」より「40代の母にプレゼントしたい娘」）
- 自然言語クエリの想定（例:「義母への母の日 5000円以下」）に答えられる語彙を含める

# 出力スキーマ (JSONのみを出力。前後の説明文は不要)
{
  "long_description": "300-500字の商品紹介。情景・触感・贈る場面を描写",
  "use_case_tags": ["母の日", "誕生日", "..."],
  "persona_tags": ["40代女性", "義母", "..."],
  "occasion_copies": [
    {"scene": "母の日", "copy": "..."}
  ],
  "faqs": [
    {"q": "...", "a": "..."}
  ],
  "ai_keywords": ["...自然言語クエリ語..."],
  "styling_tips": "コーディネート・使い方提案 100-200字"
}
"""

ENRICH_FIELDS = [
    "long_description",
    "use_case_tags",
    "persona_tags",
    "occasion_copies",
    "faqs",
    "ai_keywords",
    "styling_tips",
]


def enrich_product(client: anthropic.Anthropic, row: dict) -> dict:
    user_msg = f"""# 商品データ

商品管理番号: {row.get('商品管理番号', '')}
商品名: {row.get('商品名', '')}
カテゴリ: {row.get('カテゴリ', '')}
価格(税込): {row.get('価格', '')}
在庫数: {row.get('在庫数', '')}
ブランド: {row.get('ブランド', '')}
素材: {row.get('素材', '')}
サイズ: {row.get('サイズ', '')}
色/バリエーション: {row.get('バリエーション', '')}
既存商品説明: {row.get('商品説明', '')}
レビュー数: {row.get('レビュー数', '')}
平均評価: {row.get('平均評価', '')}
売上ランキング: {row.get('売上ランキング', '')}

上記商品をギフト用途で楽天AIエージェントが推薦しやすいよう、システムプロンプトのスキーマで返してください。"""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def score_priority(row: dict) -> int:
    """在庫あり × 売れ筋 × レビューで優先度スコア。在庫なしは -1。"""

    def _int(key, default):
        try:
            return int(str(row.get(key, default)).strip() or default)
        except ValueError:
            return default

    stock = _int("在庫数", 0)
    rank = _int("売上ランキング", 99999)
    reviews = _int("レビュー数", 0)
    if stock <= 0:
        return -1
    return reviews * 10 - rank


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY 環境変数を設定してください")

    client = anthropic.Anthropic(api_key=api_key)

    with open(args.input, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    rows = [r for r in rows if score_priority(r) >= 0]
    rows.sort(key=score_priority, reverse=True)
    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        sys.exit("処理対象の商品がありません（全件在庫切れか入力が空）")

    out_fields = list(rows[0].keys()) + ENRICH_FIELDS
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            name = (row.get("商品名") or "")[:30]
            print(f"[{i}/{len(rows)}] {row.get('商品管理番号')} {name}", file=sys.stderr)
            try:
                enriched = enrich_product(client, row)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                continue
            out = dict(row)
            for k in ENRICH_FIELDS:
                v = enriched.get(k, "")
                out[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            writer.writerow(out)
            print("  OK", file=sys.stderr)


if __name__ == "__main__":
    main()
