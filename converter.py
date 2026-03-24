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
        in_heredoc = False
        heredoc_marker = ""
        in_line_comment = False
        in_block_comment = False
        
        while end_index < len(hcl_content) and brace_count > 0:
            char = hcl_content[end_index]
            next_char = hcl_content[end_index+1] if end_index+1 < len(hcl_content) else ''
            
            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                end_index += 1
                continue
                
            if in_block_comment:
                if char == '*' and next_char == '/':
                    in_block_comment = False
                    end_index += 1 # skip '/'
                end_index += 1
                continue
            
            if in_heredoc:
                if char == '\n':
                    next_newline = hcl_content.find('\n', end_index + 1)
                    if next_newline == -1:
                        next_newline = len(hcl_content)
                    line = hcl_content[end_index+1:next_newline]
                    if line.strip() == heredoc_marker:
                        in_heredoc = False
                        end_index = next_newline - 1
                end_index += 1
                continue

            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"':
                in_string = not in_string
            elif not in_string:
                # コメントの開始判定
                if char == '#':
                    in_line_comment = True
                elif char == '/' and next_char == '/':
                    in_line_comment = True
                    end_index += 1
                elif char == '/' and next_char == '*':
                    in_block_comment = True
                    end_index += 1
                elif char == '<' and next_char == '<':
                    marker_match = re.match(r'<<-?([A-Za-z0-9_]+)', hcl_content[end_index:])
                    if marker_match:
                        in_heredoc = True
                        heredoc_marker = marker_match.group(1)
                        end_index += len(marker_match.group(0)) - 1
                elif char == '{':
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
        
        in_heredoc = False
        exclude_current_heredoc = False
        heredoc_marker = ""
        
        for line in body.split('\n'):
            stripped = line.strip()
            
            # Heredoc中（通常 or 除外中）の処理
            if in_heredoc:
                if not exclude_current_heredoc:
                    properties.append(line)
                if stripped == heredoc_marker:
                    in_heredoc = False
                    exclude_current_heredoc = False
                continue
            
            # Heredocの開始チェック
            heredoc_match = re.search(r'<<-?([A-Za-z0-9_]+)', stripped)
            if heredoc_match:
                heredoc_marker = heredoc_match.group(1)
                
                # キーの抽出ができれば除外判定を行う (key = <<-EOT)
                if '=' in stripped:
                    parts = stripped.split('=', 1)
                    key = parts[0].strip().strip('"')
                    current_full_path = ".".join([p for p in path_stack if not (p.startswith('"') and p.endswith('"'))] + [key])
                    
                    if current_full_path in read_only_attrs or key in read_only_attrs:
                        # 除外対象のHeredocは中身含めて出力しない
                        excluded_found[f"{res_type}.{res_name}.{current_full_path}"] = "<<-Heredoc Content>>"
                        in_heredoc = True
                        exclude_current_heredoc = True
                        continue
                
                in_heredoc = True
                exclude_current_heredoc = False
                properties.append(line)
                continue
            
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
