import streamlit as st
import pandas as pd
from core.config import MODEL_LIST
from ui.components import (
    render_kpi_row, render_csv_template_download,
    generate_zip_buffer, render_model_summary_table, render_financial_indicators_table,
)
from outputs.chart_generator import (
    plot_power_schedule_heatmap, plot_cumulative_cashflow_and_profit,
    plot_financial_indicators,
)


def render_sidebar():
    st.sidebar.header("⚙️ 运营参数设置")
    unit_count = st.sidebar.number_input("设备数量 (台)", min_value=1, value=1, key="sidebar_unit_count")
    exchange_rate = st.sidebar.number_input("欧元兑换汇率", min_value=1.0, value=7.8, step=0.1, key="sidebar_exchange_rate")
    discharge_ratio = st.sidebar.number_input("放电价格折扣率 (默认1.0)", value=1.0, step=0.01, key="sidebar_discharge_ratio")

    st.sidebar.markdown("---")
    st.sidebar.header("📋 数据准备")
    render_csv_template_download()

    st.sidebar.markdown("---")
    st.sidebar.header("ℹ️ 设备参数参考")
    with st.sidebar.expander("查看设备规格"):
        st.markdown("""
        | 型号 | 功率 | 额定容量 | 实际可用 |
        |------|------|----------|----------|
        | S1   | 100kW | 225kWh | 235kWh |
        | S2   | 130kW | 261kWh | 271kWh |
        | X3   | 418kW | 836kWh | 876kWh |
        """)

    return unit_count, exchange_rate, discharge_ratio


def build_summary_kpis(data_results):
    payback_data = data_results["payback_data"]
    model_finance = data_results["model_finance"]
    result = data_results["result"]

    kpis = []
    for model_data in payback_data["models"]:
        model_name = model_data["name"]
        total_profit = model_data["total_row"]["value"]
        payback = model_finance[model_name].get("payback")
        payback_str = f"{payback:.1f}月" if payback else "未回本"

        kpis.append({
            "title": f"📊 {model_name} 总收益",
            "value": f"{total_profit:.2f}",
            "unit": "万欧元",
        })
        kpis.append({
            "title": f"⏱️ {model_name} 回收周期",
            "value": payback_str,
            "unit": "",
        })

    total_dates = len(result.get("dates", []))
    kpis.append({
        "title": "📅 分析天数",
        "value": str(total_dates),
        "unit": "天",
    })

    return kpis


def render_dashboard(data_results):
    st.markdown("---")
    st.header("📊 分析结果看板")

    kpis = build_summary_kpis(data_results)
    render_kpi_row(kpis)

    result = data_results["result"]
    model_finance = data_results["model_finance"]
    payback_data = data_results["payback_data"]

    st.markdown("---")
    st.subheader("📋 电价数据预览（前20条）")
    preview_df = pd.DataFrame(result["price_rows"][:20], columns=result["price_headers"])
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "💰 收益与现金流", "📊 财务指标",
        "🔋 充放电调度", "📦 报表下载"
    ])

    with tab1:
        st.subheader("📋 投资回收与收益汇总")
        render_model_summary_table(payback_data, model_finance)

        st.markdown("---")
        st.subheader("📈 累计现金流与月度净收益")
        fig_cf = plot_cumulative_cashflow_and_profit(model_finance, result["sorted_year_months"])
        st.plotly_chart(fig_cf, use_container_width=True)

        st.markdown("---")
        st.subheader("📊 月度收益明细表")
        profit_table = {"月份": result["sorted_year_months"]}
        for model in MODEL_LIST:
            if model in model_finance:
                profit_table[f"{model} 月度净收益（万欧元）"] = [
                    round(v, 2) for v in model_finance[model]["monthly_profit"]
                ]
                profit_table[f"{model} 累计现金流（万欧元）"] = [
                    round(v, 2) for v in model_finance[model]["cum_cashflow"]
                ]
        if profit_table:
            df_profit = pd.DataFrame(profit_table)
            st.dataframe(df_profit, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("📊 财务指标趋势")
        st.caption("平均购电电价 / 平均放电电价 / 表观电价差 / 度电成本(3年折旧按月分摊)")

        model_tabs_fin = st.tabs(MODEL_LIST)
        for i, model in enumerate(MODEL_LIST):
            with model_tabs_fin[i]:
                col_chart, col_table = st.columns([3, 2])

                with col_chart:
                    fig_indicators = plot_financial_indicators(
                        payback_data, result["sorted_year_months"], model
                    )
                    st.plotly_chart(fig_indicators, use_container_width=True)

                with col_table:
                    st.markdown(f"**{model} 月度数据表**")
                    render_financial_indicators_table(
                        payback_data, result["sorted_year_months"], model
                    )

    with tab3:
        model_tabs_schedule = st.tabs(MODEL_LIST)
        for i, model in enumerate(MODEL_LIST):
            with model_tabs_schedule[i]:
                power_data = result["model_results"][model]["power_matrix_data"]
                headers = result["power_matrix_headers"]

                col_heatmap, col_table = st.columns([3, 2])

                with col_heatmap:
                    fig_schedule = plot_power_schedule_heatmap(
                        power_data, result["times"], model
                    )
                    st.plotly_chart(fig_schedule, use_container_width=True)

                with col_table:
                    st.markdown(f"**{model} 每日运行数据**")

                    date_col_idx = headers.index("日期")
                    charge_cap_idx = headers.index("充电容量(kWh)")
                    soc_left_idx = headers.index("剩余电量(kWh)")
                    charge_e_idx = headers.index("当天充电量(kWh)")
                    discharge_e_idx = headers.index("当天放电量(kWh)")
                    cycle_idx = headers.index("循环次数(次)")

                    summary_rows = []
                    for row in power_data:
                        summary_rows.append({
                            "日期": row[date_col_idx],
                            "充电容量(kWh)": round(row[charge_cap_idx], 1),
                            "剩余电量(kWh)": round(row[soc_left_idx], 1),
                            "当天充电量(kWh)": round(row[charge_e_idx], 1),
                            "当天放电量(kWh)": round(row[discharge_e_idx], 1),
                            "循环次数": round(row[cycle_idx], 3),
                        })

                    df_summary = pd.DataFrame(summary_rows)
                    st.dataframe(df_summary, use_container_width=True, hide_index=True, height=400)

    with tab4:
        st.subheader("📦 一键下载所有报表")
        st.markdown("包含以下文件：")
        for f in ["电价透视表.xlsx", "充放电功率矩阵_S1.xlsx",
                   "充放电功率矩阵_S2.xlsx", "充放电功率矩阵_X3.xlsx",
                   "投资回收期表_月报.xlsx"]:
            st.markdown(f"- {f}")

        zip_buffer = generate_zip_buffer(data_results)
        st.download_button(
            label="📦 一键下载所有生成的报表 (ZIP 压缩包)",
            data=zip_buffer.getvalue(),
            file_name="AI策略测算报告集.zip",
            mime="application/zip",
            type="primary",
        )
