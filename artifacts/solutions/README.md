# ソリューションZip置き場

このディレクトリは、GitHub Release に添付する DecisionFlow ソリューションZipの作業用置き場です。

利用者向けのインストール手順は [README.md](../../README.md) の「セットアップ手順（ソリューションインポート版）」を参照してください。

## 配布時の運用

1. Power Platform から配布用ソリューションZipをエクスポートする
2. このディレクトリにZipを一時配置して内容・ファイル名を確認する
3. GitHub の **Releases** で新しいリリースを作成する
4. **Tag: Select tag** で新しいタグ名を入力し、**Create new tag** を選択する
	- 例: `v0.1.0`, `v0.1.0-solution`, `solution-2026-05-21`
	- タグ名は空欄にできない。スペースや日本語を避け、英数字・ハイフン・ピリオドで付ける
5. Release title に利用者向けの名前を入力する
	- 例: `DecisionFlow ソリューションZip v0.1.0`
6. Release Assets にソリューションZipを添付する
7. Zipファイル本体は Git にコミットしない

Zipファイルは環境やリリース単位で差し替わるため、リポジトリにはこの README だけを保持します。
