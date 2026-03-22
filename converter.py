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
    
    # 2. 対象リソースの Read-Only 属性リストを取得 (フルパス形式: ['networks.attachments.display_name', ...])
    read_only_attrs = set(get_readonly_attributes(res_type))
    excluded_found = {}
    
    # 3. 中身のプロパティ行を抽出
    body_match = re.search(r'\{([\s\S]+)\}', hcl_content)
    if not body_match:
        return "エラー: リソースのボディが見つかりません。", []
    body = body_match.group(1)
    
    properties = []
    path_stack = [] # 現在の階層を追跡
    
    for line in body.split('\n'):
        stripped = line.strip()
        
        # コメント行や空行は無視
        if not stripped or stripped.startswith('#') or stripped.startswith('//'):
            properties.append(line)
            continue
            
        # ブロックの終了判定
        if stripped == '}' or stripped == '},' or stripped == '} }':
            if path_stack:
                path_stack.pop()
            properties.append(line)
            continue

        # key = value 形式の判定
        if '=' in stripped and not stripped.endswith('{'):
            parts = stripped.split('=', 1)
            key = parts[0].strip().strip('"')
            val = parts[1].strip()
            
            # 現在のパスを構築 (引用符で囲まれた動的なキーはパスから除外してスキーマに合わせる)
            # 例: networks."NET1".display_name -> networks.display_name
            current_full_path = ".".join([p for p in path_stack if not (p.startswith('"') and p.endswith('"'))] + [key])
            
            if current_full_path in read_only_attrs or key in read_only_attrs:
                excluded_found[current_full_path] = val
                continue
                
            properties.append(line)
            
        # block { or key = { の判定
        elif stripped.endswith('{'):
            # キーの抽出
            block_key = stripped.replace('{', '').replace('=', '').strip()
            path_stack.append(block_key)
            
            # ブロック自体が除外対象かチェック
            current_full_path = ".".join([p for p in path_stack if not (p.startswith('"') and p.endswith('"'))])
            if current_full_path in read_only_attrs:
                excluded_found[current_full_path] = "{ ... }"
                path_stack.pop() # 除外するのでスタックからも戻す
                continue
                
            # "key {" を "key = {" に変換する
            if '=' not in stripped and not (stripped.startswith('"') and ':' not in stripped):
                properties.append(line.replace('{', '= {'))
            else:
                properties.append(line)
                
        # その他（インデント維持など）
        else:
            properties.append(line)
    
    # 4. tfvars 用に再構築
    output = []
    output.append(f"{res_type} = {{")
    output.append(f"  {res_name} = {{")
    
    # 前後の空行をトリムして整形
    trimmed_properties = properties
    while trimmed_properties and not trimmed_properties[0].strip():
        trimmed_properties.pop(0)
    while trimmed_properties and not trimmed_properties[-1].strip():
        trimmed_properties.pop()

    if trimmed_properties:
        for p in trimmed_properties:
            output.append("  " + p) 
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
