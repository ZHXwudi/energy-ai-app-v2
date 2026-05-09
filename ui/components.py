import streamlit as st
import io


def render_kpi_card(title, value, unit="", delta=None, help_text=None):
    st.metric(
        label=title,
        value=f"{value} {unit}".strip(),
        delta=delta,
        help=help_text,
    )


def render_kpi_row(kpis):
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            render_kpi_card(**kpi)


def render_csv_template_download():
    template = "日期,时间,电价\n2026-01-01,00:00:00,350\n2026-01-01,01:00:00,320\n2026-01-01,02:00:00,300\n2026-01-01,03:00:00,290\n2026-01-01,04:00:00,280\n2026-01-01,05:00:00,310\n2026-01-01,06:00:00,350\n2026-01-01,07:00:00,450\n2026-01-01,08:00:00,520\n2026-01-01,09:00:00,550\n2026-01-01,10:00:00,580\n2026-01-01,11:00:00,600\n2026-01-01,12:00:00,550\n2026-01-01,13:00:00,520\n2026-01-01,14:00:00,500\n2026-01-01,15:00:00,480\n2026-01-01,16:00:00,500\n2026-01-01,17:00:00,550\n2026-01-01,18:00:00,620\n2026-01-01,19:00:00,650\n2026-01-01,20:00:00,600\n2026-01-01,21:00:00,520\n2026-01-01,22:00:00,420\n2026-01-01,23:00:00,380\n"
    st.download_button(
        label="📥 下载 CSV 模板",
        data=template,
        file_name="电价模板.csv",
        mime="text/csv",
    )


def render_upload_preview(uploaded_file):
    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode('utf-8-sig', errors='replace')
        lines = content.strip().split('\n')
        st.caption(f"已上传文件：{uploaded_file.name}，共 {len(lines)} 行数据")
        with st.expander("📋 预览上传数据（前20行）"):
            preview_lines = lines[:20]
            st.code('\n'.join(preview_lines), language='csv')


def generate_zip_buffer(data_results):
    from outputs.excel_generator import generate_price_excel, generate_power_matrix_excel, generate_payback_excel
    from core.config import MODEL_LIST
    import zipfile
    import os

    result = data_results["result"]
    generate_price_excel(
        result["price_rows"], result["price_headers"],
        result["times"], "电价透视表.xlsx",
        data_results["discharge_price_ratio"],
    )

    for model in MODEL_LIST:
        output_path = f"充放电功率矩阵_{model}.xlsx"
        generate_power_matrix_excel(
            result["model_results"][model]["power_matrix_data"],
            result["power_matrix_headers"],
            result["times"],
            output_path,
        )

    generate_payback_excel(data_results["payback_data"], "投资回收期表_月报.xlsx")

    from core.config import EXCEL_FILES
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for fn in EXCEL_FILES:
            if os.path.exists(fn):
                zip_file.write(fn)
        if os.path.exists("电价曲线图"):
            for root, dirs, files in os.walk("电价曲线图"):
                for file in files:
                    file_path = os.path.join(root, file)
                    zip_file.write(file_path, arcname=os.path.join("电价曲线图", file))

    return zip_buffer
