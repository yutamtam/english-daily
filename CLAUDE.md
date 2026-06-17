# English Daily

毎朝6時にAlexとSarahの会話形式英語ラジオをGemini APIで自動生成し、GitHub Pagesで配信するプロジェクト。

## ステータス（2026-06-17）

**稼働中** — 初回コンテンツ生成・デプロイ済み  
- サイト: https://yutamtam.github.io/english-daily/  
- リポジトリ: https://github.com/yutamtam/english-daily  
- 毎朝6時（JST）に GitHub Actions が自動実行

## 構成

```
scripts/generate.py        ← メインスクリプト（GitHub Actionsから実行）
scripts/fetch_weather.py   ← Open-Meteo天気
scripts/fetch_news.py      ← NHK World RSS
scripts/fetch_wikipedia.py ← Wikipedia On This Day
scripts/fetch_parenting.py ← Zero to Three RSS（失敗時はフォールバックトピックを使用）
scripts/send_email.py      ← Gmail SMTP通知
content/YYYY-MM-DD.json    ← 生成されたスクリプト（GitHub Actionsがコミット）
docs/index.html            ← エピソード一覧（GitHub Pages）
docs/player.html           ← 再生プレイヤー（Web Speech API）
docs/css/style.css         ← スタイル
data/vocab/                ← 語彙JSONファイル群（svl/kyokugen/shukyoku）
config.json                ← ユーザー設定（語彙レベル・場所・メールアドレス）
test_gemini.py             ← APIキーのローカルテスト用（.gitignore対象にしてもよい）
```

## 技術的な決定事項（ハマった点）

### Gemini SDK・モデル
- `google-generativeai`（旧SDK）→ `google-genai`（新SDK）に移行済み
- `gemini-2.0-flash` は無料枠が `limit: 0` になる問題あり → `gemini-2.5-flash` に変更
- API バージョンは `v1` を明示指定（`v1beta` だとクォータ問題が出た）
- 503エラー（高負荷）が出ることがあるため、4回リトライ・15秒間隔を実装済み

### GitHub Actions
- `permissions: contents: write` が必要（content/をコミットするため）
- `workflow` スコープを `gh auth refresh` で追加する必要があった

## GitHub Secrets（設定済み）

| 変数名 | 内容 |
|--------|------|
| `GEMINI_API_KEY` | Google AI Studio のAPIキー（新規プロジェクトで作成） |
| `GMAIL_USER` | yuta.m0920@gmail.com |
| `GMAIL_APP_PASSWORD` | Googleアカウントのアプリパスワード |

## 語彙レベル設定（config.json の vocab_level）

| 値 | 語彙数 | 対応ファイル |
|----|--------|------------|
| 1 | ~3,000語 | svl_01〜03 |
| 2 | ~6,000語 | svl_01〜06 |
| 3 | ~12,000語（現在の設定） | svl_01〜12 |
| 4 | ~24,000語 | svl_01〜12 + kyokugen_13〜24 |
| 5 | ~34,000語 | 全ファイル |

## 今後の改善候補（微修正メモ）

- [ ] NHK World RSSが0件を返すことがある（フィードURL要確認）
- [ ] Gmailメール通知の動作確認（アプリパスワードを再生成したため）
- [ ] プレイヤーのUI微調整（フォント・色・ボタン配置など）
- [ ] カラオケ式ハイライト（再生中の行をリアルタイムハイライト）
- [ ] 過去エピソードの一覧ソート確認
- [ ] test_gemini.py を .gitignore に追加する

## ローカルテスト方法

```bash
cd english-daily
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
python scripts/generate.py
```
