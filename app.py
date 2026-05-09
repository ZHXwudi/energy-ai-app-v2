import streamlit as st
import tempfile
import os

try:
    import pulp
except ImportError:
    st.error("错误：未找到 pulp 库。请检查运行环境（pip install pulp）。")
    st.stop()

from core.config import MODEL_LIST
from core.price_parser import parse_price_csv
from core.finance import run_all_models, calculate_finance
from ui.components import (
    render_upload_preview, render_csv_template_download, generate_zip_buffer,
)
from ui.pages import render_sidebar, render_dashboard

st.set_page_config(
    page_title="储能AI策略测算引擎",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("⚡ 储能AI策略测算引擎")
st.caption("基于 MILP（混合整数线性规划）72小时滚动优化 · 多设备型号对比 · 投资回收分析")


def clear_cached():
    st.cache_data.clear()
    st.cache_resource.clear()


def run_analysis(uploaded_file, unit_count, exchange_rate, discharge_ratio):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as tmp:
        content = uploaded_file.getvalue().decode('utf-8-sig', errors='replace')
        tmp.write(content)
        tmp_path = tmp.name

    try:
        price_by_date, times_set = parse_price_csv(tmp_path)

        if not price_by_date:
            return None, "未能从CSV中解析到有效电价数据。请检查格式：需含日期/时间/电价三列。"

        progress_container = st.empty()

        total_models = len(MODEL_LIST)
        total_dates = len(price_by_date)

        with st.status("正在运行 MILP 优化计算...", expanded=True) as status:
            status.write(f"解析到 {len(price_by_date)} 天的电价数据")
            st.write(f"正在对 {total_models} 种设备型号运行72小时滚动窗口优化...")

            progress_bar = st.progress(0, text="初始化...")

            def progress_callback(model, completed, total):
                model_idx = MODEL_LIST.index(model)
                overall = (model_idx * total + completed) / (total_models * total)
                progress_bar.progress(overall, text=f"{model} 型号: {completed}/{total} 天完成")
                status.write(f"✅ {model}：已完成 {completed}/{total} 天")

            status.write("启动 MILP 求解器...")
            result = run_all_models(
                price_by_date, unit_count, discharge_ratio,
                exchange_rate, progress_callback,
            )

            status.write("正在计算财务指标...")
            model_finance, payback_data = calculate_finance(
                result["model_results"],
                result["sorted_year_months"],
                unit_count,
                exchange_rate,
            )

            progress_bar.progress(1.0, text="✅ 计算完成！")
            status.update(label="✅ 计算完成！", state="complete", expanded=False)

        progress_container.empty()

        data_results = {
            "result": result,
            "model_finance": model_finance,
            "payback_data": payback_data,
            "discharge_price_ratio": discharge_ratio,
            "exchange_rate": exchange_rate,
            "unit_count": unit_count,
        }

        return data_results, None

    except Exception as e:
        return None, f"计算过程中发生错误：{str(e)}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


unit_count, exchange_rate, discharge_ratio = render_sidebar()

uploaded_file = st.file_uploader(
    "📁 上传电价 CSV 文件",
    type=["csv"],
    help="CSV需包含日期、时间、电价三列（电价单位：€/MWh）",
)

render_upload_preview(uploaded_file)

if uploaded_file is not None:
    if 'run_analysis' not in st.session_state:
        st.session_state.run_analysis = False

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🚀 启动分析", type="primary", use_container_width=True):
            st.session_state.run_analysis = True
    with col2:
        if st.button("🔄 重置所有", use_container_width=True):
            clear_cached()
            st.session_state.run_analysis = False
            st.rerun()

    if st.session_state.run_analysis:
        data_results, error_msg = run_analysis(
            uploaded_file, unit_count, exchange_rate, discharge_ratio,
        )

        if error_msg:
            st.error(error_msg)
        elif data_results:
            render_dashboard(data_results)
else:
    st.info("👆 请上传电价 CSV 文件后点击「启动分析」按钮开始计算。")
    with st.expander("📖 使用说明"):
        st.markdown("""
        ### 使用方法
        1. **准备数据**：准备一个 CSV 文件，包含 `日期`、`时间`、`电价` 三列
           - 日期格式：`2026-01-01`
           - 时间格式：`00:00:00`（仅支持整点时刻）
           - 电价单位：**€/MWh**（系统自动转换为 €/kWh）
        2. **设置参数**：在左侧边栏设置设备数量、汇率、放电折扣率
        3. **启动分析**：点击「启动分析」运行 MILP 优化
        4. **查看结果**：在结果看板中浏览交互式图表和数据表
        5. **下载报表**：在「报表下载」标签页一键下载所有 Excel 文件

        ### 算法原理
        - 采用**72小时滚动窗口 MILP**（混合整数线性规划）
        - 目标函数：最大化（放电收入 × 折扣率 − 充电成本 − 循环损耗）
        - 约束：充放电互斥、能量守恒（效率95%）、SOC上下限
        - 财务模型：3年折旧分摊、LCOS度电成本、投资回收期
        """)
