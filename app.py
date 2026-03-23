import streamlit as st
import pandas as pd
from converter import convert_hcl_to_tfvars
from import_generator import generate_import_blocks

def render_tfvars_converter():
    st.title("Terraform HCL ➡️ tfvars Converter")
    st.markdown("""
    `terraform plan` 等で取得したリソースブロック（HCL形式）を入力すると、
    公式ドキュメントから動的に **Read-Only / Computed 属性** を判定・自動除外し、
    `tfvars` 形式に変形して出力します。
    """)
    
    st.subheader("1. HCL を入力してください")
    st.markdown("※ 複数のリソースをまとめてペーストしても変換可能です。")
    hcl_input = st.text_area(
        "リソースのコード (例: resource \"dcnm_interface\" \"name\" { ... })",
        height=300,
        placeholder="ここにHCLをペーストしてください..."
    )
    
    if st.button("変換する (Convert)", type="primary"):
        if not hcl_input.strip():
            st.warning("HCLコードが入力されていません。")
            return
            
        with st.spinner("変換中... (複数リソースの探索とRead-Only属性の除外を行っています)"):
            tfvars_output, excluded_attrs = convert_hcl_to_tfvars(hcl_input)
            
        st.success("変換完了！")
        
        st.subheader("2. 変換結果")
        st.code(tfvars_output, language="hcl")
        
        if excluded_attrs:
            st.info("💡 以下の属性は Read-Only / Computed として自動的に除外されました:")
            df = pd.DataFrame(list(excluded_attrs.items()), columns=["属性 (Key)", "値 (Value)"])
            # st.tableの場合、長いキーが画面幅などで見切れてしまうことがあるためインタラクティブな dataframe を使用します
            st.dataframe(df, use_container_width=True)
        else:
            st.info("💡 除外された Read-Only 属性はありませんでした。")

def render_import_generator():
    st.title("Terraform Import Block Generator")
    st.markdown("""
    `terraform import` コマンドのリストを、Terraform 1.5以降の `imports.tf` 用の `import` ブロックに一括変換します。
    """)
    
    st.subheader("1. `terraform import` コマンドを入力してください")
    tf_input = st.text_area(
        "コマンドのリスト (例: terraform import ndfc_template.default_network_universal Default_Network_Universal)",
        height=300,
        placeholder="ここにコマンドを複数行ペーストしてください..."
    )
    
    if st.button("importブロックを生成する", type="primary"):
        if not tf_input.strip():
            st.warning("コマンドが入力されていません。")
            return
            
        import_output = generate_import_blocks(tf_input)
        
        if not import_output:
            st.warning("`terraform import` コマンドが見つかりませんでした。入力内容をご確認ください。")
            return
            
        st.success("生成完了！")
        
        st.subheader("2. 生成結果 (imports.tf用)")
        st.markdown("右上のコピーボタンからコピーして `imports.tf` にそのまま貼り付けて利用できます。")
        st.code(import_output, language="hcl")

def main():
    st.set_page_config(page_title="Terraform Helper Tools", page_icon="⚙️", layout="wide")
    
    st.sidebar.title("メニュー")
    mode = st.sidebar.radio(
        "機能を選択してください:",
        ["tfvars 変換", "import ブロック生成"]
    )
    
    if mode == "tfvars 変換":
        render_tfvars_converter()
    elif mode == "import ブロック生成":
        render_import_generator()

if __name__ == '__main__':
    main()
