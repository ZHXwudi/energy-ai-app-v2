import streamlit as st
import pandas as pd
from core.config import MODEL_LIST
from ui.components import render_kpi_row, render_csv_template_download, render_upload_preview, generate_zip_buffer
from outputs.chart_generator import (
    plot_price_curves_interactive, plot_price_heatmap,
    plot_power_schedule_heatmap, plot_cumulative_cashflow,
    plot_monthly_profit_bar, plot_lcos_comparison,
    plot_model_kpi_summary,
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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 模型对比", "💰 现金流分析", "⚡ 电价分析",
        "🔋 充放电调度", "📊 月度明细", "📦 报表下载"
    ])

    with tab1:
        st.subheader("设备型号综合对比")
        fig_summary = plot_model_kpi_summary(model_finance, payback_data)
        st.plotly_chart(fig_summary, use_container_width=True)

        st.subheader("度电成本 (LCOS) 趋势")
        fig_lcos = plot_lcos_comparison(payback_data, result["sorted_year_months"])
        st.plotly_chart(fig_lcos, use_container_width=True)

    with tab2:
        st.subheader("累计现金流趋势")
        fig_cf = plot_cumulative_cashflow(model_finance, result["sorted_year_months"])
        st.plotly_chart(fig_cf, use_container_width=True)

        st.subheader("月度净收益对比")
        fig_profit = plot_monthly_profit_bar(model_finance, result["sorted_year_months"])
        st.plotly_chart(fig_profit, use_container_width=True)

        col1, col2 = st.columns(2)
        for i, model in enumerate(MODEL_LIST):
            with [col1, col2][i % 2]:
                fin = model_finance.get(model, {})
                payback = fin.get("payback")
                payback_str = f"{payback:.1f} 个月" if payback else "未回本"
                st.metric(
                    label=f"{model} 回收周期",
                    value=payback_str,
                    delta=None,
                )
                if fin.get("cum_cashflow"):
                    st.caption(f"最终累计现金流: {fin['cum_cashflow'][-1]:.2f} 万欧元")

    with tab3:
        st.subheader("电价热力图")
        fig_heatmap = plot_price_heatmap(result["price_rows"], result["times"])
        st.plotly_chart(fig_heatmap, use_container_width=True)

        st.subheader("电价曲线图")
        price_figures = plot_price_curves_interactive(result["price_rows"], result["times"])
        for key, fig in price_figures.items():
            month_label = key.replace("price_curves_", "").replace("month_", "")
            st.caption(f"{month_label}月")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("电价数据表")
        df_prices = pd.DataFrame(result["price_rows"], columns=result["price_headers"])
        st.dataframe(df_prices, use_container_width=True, height=300)

    with tab4:
        model_tabs = st.tabs(MODEL_LIST)
        for i, model in enumerate(MODEL_LIST):
            with model_tabs[i]:
                power_data = result["model_results"][model]["power_matrix_data"]
                fig_schedule = plot_power_schedule_heatmap(
                    power_data, result["times"], model
                )
                st.plotly_chart(fig_schedule, use_container_width=True)

                df_power = pd.DataFrame(power_data, columns=result["power_matrix_headers"])
                st.dataframe(df_power, use_container_width=True, height=300)

    with tab5:
        for model_data in payback_data["models"]:
            st.subheader(f"{model_data['name']} 月度指标")
            rows_data = {}
            for row in model_data["rows"]:
                rows_data[row["label"]] = row["values"]
            df_monthly = pd.DataFrame(rows_data, index=result["sorted_year_months"]).T
            st.dataframe(df_monthly, use_container_width=True)

    with tab6:
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
