import requests
import re
import functools

@functools.lru_cache(maxsize=32)
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
                current_schema_path = ""
                current_section = "" # "Required", "Optional", "Read-Only"
                
                for line in lines:
                    stripped = line.strip()
                    lower_line = stripped.lower()
                    
                    if not stripped:
                        continue
                    
                    # 階層（Nested Schema）の検知
                    schema_match = re.search(r'Nested Schema for `?([\w\.]+)`?', line)
                    if schema_match:
                        current_schema_path = schema_match.group(1)
                        in_readonly_section = False
                        current_section = ""
                        continue
                    
                    # セクション（Required/Optional/Read-Only）の検知 / 見出しによるリセット
                    if stripped.startswith('#') or stripped.endswith(':'):
                        clean_header = stripped.replace('#', '').replace('*', '').strip().lower()
                        
                        # 明示的な属性セクションの開始
                        if 'required' in clean_header:
                            current_section = "Required"
                            in_readonly_section = False
                        elif 'optional' in clean_header:
                            current_section = "Optional"
                            in_readonly_section = False
                        elif 'read-only' in clean_header or 'computed' in clean_header:
                            current_section = "Read-Only"
                            in_readonly_section = True
                        elif stripped.startswith('#'):
                            # それ以外の見出し（## Template Parametersなど）が出現したら状態をリセット
                            current_section = ""
                            in_readonly_section = False
                    
                    if '`' in stripped:
                        match = re.search(r'`([a-zA-Z0-9_]+)`', stripped)
                        if match:
                            attr_name = match.group(1)
                            
                            # 除外判定ルール:
                            # 1. 明示的な 'Read-Only' または 'Computed' セクションにいる場合
                            # 2. セクションが不明だが、説明文に 'read-only' 等が含まれる場合 (念のため残すが、Optional内は避ける)
                            is_readonly = in_readonly_section
                            
                            if not is_readonly and current_section not in ["Optional", "Required"]:
                                if 'read-only' in lower_line or 'computed' in lower_line or 'read only' in lower_line:
                                    is_readonly = True
                            
                            if is_readonly:
                                full_path = f"{current_schema_path}.{attr_name}" if current_schema_path else attr_name
                                read_only_attrs.add(full_path)
                                if not current_schema_path:
                                    read_only_attrs.add(attr_name)
                                
                break 
        except Exception as e:
            print(f"URL {url} 取得エラー: {e}")
            pass
            
    if not html_fetched:
        print("💡 [警告] 動的なドキュメント取得に失敗しました。")
        
    return list(read_only_attrs)

if __name__ == '__main__':
    print("ndfc_inventory_devices:", get_readonly_attributes("ndfc_inventory_devices"))
