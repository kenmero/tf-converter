import re
from scraper import get_readonly_attributes

def extract_resource_blocks(hcl_content: str) -> list[tuple[str, str, str]]:
    """
    HCL文字列からすべての resource ブロックを抽出し、
    (リソース種別, リソース名, ブロック内のHCL文字列) のリストを返す。
    """
    blocks = []
    pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
    
    pos = 0
    while True:
        match = pattern.search(hcl_content, pos)
        if not match:
            break
            
        res_type = match.group(1)
        res_name = match.group(2)
        start_index = match.end()
        
        brace_count = 1
        end_index = start_index
        in_string = False
        escape_next = False
        
        while end_index < len(hcl_content) and brace_count > 0:
            char = hcl_content[end_index]
            
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
            end_index += 1
            
        # 最後の '}' を含めないように切り出す
        if brace_count == 0:
            body = hcl_content[start_index:end_index-1]
            blocks.append((res_type, res_name, body))
        else:
            body = hcl_content[start_index:]
            blocks.append((res_type, res_name, body))
            
        pos = end_index
        
    return blocks

def convert_hcl_to_tfvars(hcl_content: str) -> tuple[str, dict[str, str]]:
    """
    HCLの1つまたは複数のresourceブロックをパースし、tfvars形式に変換する。
    その際、Read-Onlyとみなされる属性は除外する。
    
    Returns:
        (変換後の文字列, 除外された属性名の辞書 {キー: 値})
    """
    blocks = extract_resource_blocks(hcl_content)
    if not blocks:
        return "エラー: リソース定義（resource \"type\" \"name\" {）が見つかりません。", {}
        
    all_outputs = []
    all_excluded = {}
    
    for res_type, res_name, body in blocks:
        # 動的・ネストされた属性も考慮したRead-Only属性の取得 (キャッシュ利用)
        read_only_attrs = set(get_readonly_attributes(res_type))
        excluded_found = {}
        
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
                current_full_path = ".".join([p for p in path_stack if not (p.startswith('"') and p.endswith('"'))] + [key])
                
                if current_full_path in read_only_attrs or key in read_only_attrs:
                    excluded_found[f"{res_type}.{res_name}.{current_full_path}"] = val
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
                    excluded_found[f"{res_type}.{res_name}.{current_full_path}"] = "{ ... }"
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
        
        all_outputs.append("\n".join(output))
        all_excluded.update(excluded_found)
        
    return "\n\n".join(all_outputs), all_excluded

if __name__ == '__main__':
    # テスト用
    sample = """
resource "dcnm_interface" "first" {
  id            = "port-channel501"
  policy        = "int_port_channel_access_host_11_1"
  type          = "port-channel"
  name          = "port-channel501"
  fabric_name   = "fab1"
  switch_name_1 = "leaf1"
  last_updated  = "2023-10-01"
}

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
