import requests
import re

def get_readonly_attributes(resource_type: str) -> list[str]:
    """
    Terraform Registry API を使用して対象リソースの正確なドキュメントパスを取得し、
    GitHubのRaw Markdownから 'Read-Only' 属性を動的にスクレイピングします。
    """
    parts = resource_type.split('_', 1)
    prefix = parts[0] if len(parts) > 1 else 'dcnm'
    suffix = parts[1] if len(parts) > 1 else resource_type
    
    # 最小限の初期化
    read_only_attrs = set(["id"])
    
    # 1. Terraform Registry APIからプロバイダ情報を取得
    provider_name = f"CiscoDevNet/{prefix}"
    api_url = f"https://registry.terraform.io/v1/providers/{provider_name}"
    
    doc_path = None
    
    try:
        # タイムアウト付きでAPIリクエスト
        res = requests.get(api_url, timeout=(3.0, 5.0))
        if res.status_code == 200:
            data = res.json()
            # docs リストから該当リソースのパスを検索
            for doc in data.get("docs", []):
                # category が resources であり、さらに slug か title が suffix に一致するもの
                if doc.get("category") == "resources" and (doc.get("title") == suffix or doc.get("slug") == suffix):
                    doc_path = doc.get("path")
                    break
    except Exception as e:
        print(f"Registry API 接続エラー: {e}")
        
    if not doc_path:
        # APIから取得できなかった場合の推測パス（フォールバック）
        doc_path = f"website/docs/r/{suffix}.html.markdown"

    repo_path = f"CiscoDevNet/terraform-provider-{prefix}"
    
    # 2. Github Raw から Markdown を取得
    urls = [
        f"https://raw.githubusercontent.com/{repo_path}/main/{doc_path}",
        f"https://raw.githubusercontent.com/{repo_path}/master/{doc_path}"
    ]
    
    html_fetched = False
    for url in urls:
        try:
            response = requests.get(url, timeout=(3.0, 5.0))
            if response.status_code == 200:
                lines = response.text.split('\n')
                html_fetched = True
                
                in_readonly_section = False
                
                for line in lines:
                    stripped = line.strip()
                    lower_line = stripped.lower()
                    
                    # 空行は状態を維持したままスキップ
                    if not stripped:
                        continue
                        
                    # セクションの終了判定：別の見出し(#)や、'Optional:' などのコロンで終わる行が来た場合
                    if in_readonly_section:
                        if stripped.startswith('#') or (stripped.endswith(':') and 'read-only' not in lower_line and 'computed' not in lower_line):
                            in_readonly_section = False
                    
                    # Read-Only セクションの開始を検知
                    # パターン1: ### Read-Only
                    # パターン2: Read-Only:
                    clean_lower = lower_line.replace('*', '').replace('#', '').strip()
                    if clean_lower == 'read-only' or clean_lower == 'read-only:' or clean_lower == 'computed' or clean_lower == 'computed:':
                        in_readonly_section = True
                        continue
                    
                    if '`' in stripped:
                        match = re.search(r'`([a-zA-Z0-9_]+)`', stripped)
                        if match:
                            attr_name = match.group(1)
                            # 行自体がread-onlyを含んでいるか、現在read-onlyセクションの中なら追加
                            if 'read-only' in lower_line or 'computed' in lower_line or 'read only' in lower_line or in_readonly_section:
                                read_only_attrs.add(attr_name)
                                
                break # 取得に成功したら別ブランチは試さない
        except Exception as e:
            print(f"URL {url} 取得エラー: {e}")
            pass
            
    if not html_fetched:
        print("💡 [警告] 動的なドキュメント取得に失敗しました。")
        
    return list(read_only_attrs)

if __name__ == '__main__':
    print("ndfc_inventory_devices:", get_readonly_attributes("ndfc_inventory_devices"))
