import re
from scraper import get_readonly_attributes

def convert_hcl_to_tfvars(hcl_content: str) -> tuple[str, dict[str, str]]:
    """
    HCLのresourceブロックをパースし、tfvars形式に変換する。
    その際、Read-Onlyとみなされる属性は除外する。
    
    Returns:
        (変換後の文字列, 除外された属性名の辞書 {キー: 値})
    """
    
    # 1. resource の種類と名前を抽出
    # resource "dcnm_interface" "second" { ... }
    header_match = re.search(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', hcl_content)
    if not header_match:
        return "エラー: リソース定義（resource \"type\" \"name\" {）が見つかりません。", []
    
    res_type = header_match.group(1)
    res_name = header_match.group(2)
    
    # 2. 対象リソースの Read-Only 属性リストを取得
    read_only_attrs = get_readonly_attributes(res_type)
    excluded_found = {}
    
    # 3. 中身のプロパティ行を抽出
    # ネストされたブロック（{}）内の詳細パースは今回簡易的にスキップし、トップレベルのキーバリューを解析します
    body_match = re.search(r'\{([\s\S]+)\}', hcl_content)
    if not body_match:
        return "エラー: リソースのボディが見つかりません。", []
    body = body_match.group(1)
    
    properties = []
    for line in body.split('\n'):
        stripped = line.strip()
        
        # コメント行や空行は無視
        if not stripped or stripped.startswith('#') or stripped.startswith('//'):
            continue
            
        # key = value 形式の判定 (ブロックの開始ではないか確認)
        if '=' in stripped and not stripped.endswith('{'):
            parts = stripped.split('=', 1)
            key = parts[0].strip()
            val = parts[1].strip()
            
            if key in read_only_attrs:
                excluded_found[key] = val
                continue
                
            properties.append(line)
            
        # block { の判定
        elif stripped.endswith('{'):
            block_key = stripped.replace('{', '').replace('=', '').strip()
            if block_key in read_only_attrs:
                excluded_found[block_key] = "{ ... }"
                continue
                
            # "key {" を "key = {" に変換する
            if '=' not in stripped:
                properties.append(line.replace('{', '= {'))
            else:
                properties.append(line)
                
        # 閉じカッコなど
        else:
            properties.append(line)
    
    # 4. tfvars 用に再構築
    output = []
    output.append(f"{res_type} = {{")
    output.append(f"  {res_name} = {{")
    if properties:
        for p in properties:
            output.append("  " + p) # 元のインデントにもう一段階字下げを追加
    output.append("  }")
    output.append("}")
    
    return "\n".join(output), excluded_found

if __name__ == '__main__':
    # テスト用
    sample = """
resource "dcnm_interface" "second" {
  id            = "port-channel502"
  policy        = "int_port_channel_access_host_11_1"
  type          = "port-channel"
  name          = "port-channel502"
  fabric_name   = "fab2"
  switch_name_1 = "leaf2"
  last_updated  = "2023-10-01"
}
    """
    res, exc = convert_hcl_to_tfvars(sample)
    print("EXCLUDED:", exc)
    print("RESULT:\\n", res)
