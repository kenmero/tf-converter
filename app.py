import streamlit as st
from converter import convert_hcl_to_tfvars

def main():
    st.set_page_config(page_title="Terraform to tfvars Converter", page_icon="⚙️", layout="centered")
    
    st.title("Terraform HCL ➡️ tfvars Converter")
    st.markdown("""
    `terraform plan` 等で取得したリソースブロック（HCL形式）を入力すると、
    公式ドキュメントから動的に **Read-Only / Computed 属性** を判定・自動除外し、
    `tfvars` 形式に変形して出力します。
    """)
    
    st.subheader("1. HCL を入力してください")
    hcl_input = st.text_area(
        "リソースのコード (例: resource \"dcnm_interface\" \"name\" { ... })",
        height=300,
        placeholder="ここにHCLをペーストしてください..."
    )
    
    if st.button("変換する (Convert)", type="primary"):
        if not hcl_input.strip():
            st.warning("HCLコードが入力されていません。")
            return
            
        with st.spinner("変換中... (Read-Only属性を探索しています)"):
            tfvars_output, excluded_attrs = convert_hcl_to_tfvars(hcl_input)
            
        st.success("変換完了！")
        
        st.subheader("2. 変換結果")
        st.code(tfvars_output, language="hcl")
        
        if excluded_attrs:
            st.info("💡 以下の属性は Read-Only / Computed として自動的に除外されました:")
            import pandas as pd
            df = pd.DataFrame(list(excluded_attrs.items()), columns=["属性 (Key)", "値 (Value)"])
            st.table(df)
        else:
            st.info("💡 除外された Read-Only 属性はありませんでした。")

if __name__ == '__main__':
    main()
