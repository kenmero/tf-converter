import re

def generate_import_blocks(tf_content: str) -> str:
    """
    terraform import コマンドのリストから、Terraform 1.5以降の import ブロックを生成します。
    例: terraform import ndfc_template.default_network_universal Default_Network_Universal
    """
    pattern = re.compile(r'terraform\s+import\s+([^\s]+)\s+(.+)$')
    
    outputs = []
    
    for line in tf_content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        match = pattern.search(line)
        if match:
            to_path = match.group(1)
            raw_id = match.group(2).strip()
            
            # もしクォートで囲まれていたら外す ("id" や 'id' の場合)
            if (raw_id.startswith('"') and raw_id.endswith('"')) or \
               (raw_id.startswith("'") and raw_id.endswith("'")):
                raw_id = raw_id[1:-1]
            
            block = (
                "import {\n"
                f"  id = \"{raw_id}\"\n"
                f"  to = {to_path}\n"
                "}"
            )
            outputs.append(block)
            
    if not outputs:
        return ""
        
    return "\n\n".join(outputs)
