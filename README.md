# Terraform to tfvars Converter

`terraform plan` やリソース定義 (HCL) から、不要な Read-Only 属性や Computed 属性を自動的に除外し、変数 (`tfvars`) 形式へとスマートに変換するStreamlit製のローカルWebアプリケーションです。

## 特徴
- **動的スクレイピング**: Terraform Registry API を通じて対象リソース（`dcnm_*` や `ndfc_*` など）の最新の公式ドキュメントURLを特定し、GitHub上のMarkdownからRead-Only属性を直接・動的に抽出して除外判定を行います。
- **フォールバック機構**: オフライン環境や通信エラー時には、あらかじめ組み込まれているプロバイダー特有の Read-Only・Computed な基本属性（`config_status`, `id`, `uuid` など）を元に除外処理を安全・確実に行います。
- **インデントやネストを維持**: 単純なキーバリューのパースだけでなく、`switch_config { ... }` のようなネストブロックを維持し、インデントずれを起こさず `tfvars` 形式を出力します。

## 動作環境
- Python 3.x
- `pip`

## インストールと起動手順

1. リポジトリのクローンまたはディレクトリへの移動:
   ```bash
   cd tf-converter
   ```

2. 仮想環境の作成とパッケージのインストール（推奨）:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. アプリケーションの起動:
   ```bash
   streamlit run app.py
   ```
   起動後、ブラウザで `http://localhost:8501` にアクセスしてください。

## 使い方
1. 表示されたテキストエリアに、`terraform plan` 等から取得したHCLのリソース定義（例: `resource "ndfc_inventory_devices" "test" { ... }`）をペーストします。
2. 「変換する (Convert)」ボタンを押します。
3. バックグラウンドで自動的に公式ドキュメントの解析が行われ、Read-Onlyとみなされた属性（`id`, `config_status` など）が取り除かれます。
4. 出力エリアに `tfvars` 用にパースされた変数代入ブロックが表示されますので、そのままコピーしてご利用ください。除外した属性とその値は画面下のテーブルで確認できます！
