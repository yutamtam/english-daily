# English Daily

毎朝6時にAlexとSarahの会話形式英語ラジオをGemini APIで自動生成し、GitHub Pagesで配信するプロジェクト。

## 構成

```
scripts/generate.py       ← メインスクリプト（GitHub Actionsから実行）
scripts/fetch_weather.py  ← Open-Meteo天気
scripts/fetch_news.py     ← NHK World RSS
scripts/fetch_wikipedia.py← Wikipedia On This Day
scripts/fetch_parenting.py← Zero to Three RSS（失敗時はフォールバックトピックを使用）
scripts/send_email.py     ← Gmail SMTP通知
content/YYYY-MM-DD.json   ← 生成されたスクリプト（GitHub Actionsがコミット）
docs/                     ← GitHub Pages（index.html・player.html）
data/vocab/               ← 語彙JSONファイル群
config.json               ← ユーザー設定（語彙レベル・場所・メールアドレス）
```

## 必要な環境変数（GitHub Secrets）

| 変数名 | 内容 |
|--------|------|
| `GEMINI_API_KEY` | Google Gemini APIキー |
| `GMAIL_USER` | 送信元Gmailアドレス |
| `GMAIL_APP_PASSWORD` | Googleアカウントのアプリパスワード |

## GitHub Pages の URL

```
https://<GitHubユーザー名>.github.io/english-daily/
```

player.html の `REPO` 変数と `REPO_RAW` 変数をGitHubユーザー名に合わせて変更すること。

## 語彙レベル設定（config.json の vocab_level）

| 値 | 語彙数 | 対応ファイル |
|----|--------|------------|
| 1 | ~3,000語 | svl_01〜03 |
| 2 | ~6,000語 | svl_01〜06 |
| 3 | ~12,000語 | svl_01〜12 |
| 4 | ~24,000語 | svl_01〜12 + kyokugen_13〜24 |
| 5 | ~34,000語 | 全ファイル |

## ローカルテスト方法

```bash
cd english-daily
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="your-app-password"
python scripts/generate.py
```

## GitHub セットアップ手順

1. GitHubで `english-daily` リポジトリを作成（publicにすること）
2. このフォルダをpushする
3. Settings → Pages → Source を `main` ブランチの `docs/` フォルダに設定
4. Settings → Secrets and variables → Actions に上記3つのSecretsを追加
5. Actions タブで手動実行して動作確認
