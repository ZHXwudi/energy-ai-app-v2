import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
from core.config import MODEL_LIST


def plot_price_curves_interactive(price_rows, times):
    time_minutes = []
    time_labels = []
    for t in times:
        h, m, s = map(int, t.split(':'))
        time_minutes.append(h * 60 + m)
        time_labels.append(t)

    month_data = {1: [], 2: []}
    for row in price_rows:
        date_str = row[0]
        prices = row[1:1 + len(times)]
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if date.month in month_data:
            month_data[date.month].append((date_str, prices))

    figures = {}
    for month in [1, 2]:
        data = month_data[month]
        if not data:
            continue

        fig = go.Figure()
        for date_str, prices in data:
            fig.add_trace(go.Scatter(
                x=time_labels,
                y=prices,
                mode='lines',
                name=date_str,
                line=dict(width=1.5),
            ))

        fig.update_layout(
            title=f"{month}月 每日电价曲线汇总",
            xaxis_title="时刻",
            yaxis_title="电价 (€/kWh)",
            hovermode="x unified",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
            height=500,
            margin=dict(r=150),
        )
        figures[f"price_curves_month_{month}"] = fig

    return figures


def plot_price_heatmap(price_rows, times):
    dates = [row[0] for row in price_rows]
    z_data = [row[1:1 + len(times)] for row in price_rows]

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=times,
        y=dates,
        colorscale='RdYlGn',
        colorbar=dict(title="€/kWh"),
        hovertemplate='日期: %{y}<br>时刻: %{x}<br>电价: %{z:.4f} €/kWh<extra></extra>',
    ))

    fig.update_layout(
        title="电价热力图",
        xaxis_title="时刻",
        yaxis_title="日期",
        height=max(400, len(dates) * 20),
    )

    return fig


def plot_power_schedule_heatmap(power_matrix_data, times, model_name):
    dates = [row[0] for row in power_matrix_data]
    z_data = [row[1:1 + len(times)] for row in power_matrix_data]

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=times,
        y=dates,
        colorscale=[
            [0, 'rgb(198, 239, 206)'],
            [0.5, 'rgb(255, 255, 255)'],
            [1, 'rgb(255, 235, 156)'],
        ],
        zmid=0,
        colorbar=dict(title="kW (正=放电, 负=充电)"),
        hovertemplate='日期: %{y}<br>时刻: %{x}<br>功率: %{z:.1f} kW<extra></extra>',
    ))

    fig.update_layout(
        title=f"{model_name} 充放电功率热力图",
        xaxis_title="时刻",
        yaxis_title="日期",
        height=max(400, len(dates) * 20),
    )

    return fig


def plot_cumulative_cashflow(model_finance, sorted_year_months):
    fig = go.Figure()

    colors = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    for model in MODEL_LIST:
        if model in model_finance:
            cum_cf = model_finance[model]["cum_cashflow"]
            fig.add_trace(go.Scatter(
                x=sorted_year_months,
                y=cum_cf,
                mode='lines+markers',
                name=f"{model} 累计现金流",
                line=dict(width=3, color=colors.get(model, "#333")),
                marker=dict(size=8),
            ))

    payback_annotations = []
    for model in MODEL_LIST:
        if model in model_finance:
            payback = model_finance[model].get("payback")
            if payback is not None and 0 < payback <= len(sorted_year_months):
                idx = int(payback) - 1
                payback_annotations.append(dict(
                    x=sorted_year_months[min(idx, len(sorted_year_months) - 1)],
                    y=0,
                    text=f"{model} 回本",
                    showarrow=True,
                    arrowhead=2,
                    ax=20,
                    ay=-40,
                ))

    fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5)

    fig.update_layout(
        title="累计现金流趋势",
        xaxis_title="月份",
        yaxis_title="累计现金流（万欧元）",
        hovermode="x unified",
        height=450,
        annotations=payback_annotations,
    )

    return fig


def plot_monthly_profit_bar(model_finance, sorted_year_months):
    fig = go.Figure()

    colors = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    for model in MODEL_LIST:
        if model in model_finance:
            monthly_profit = model_finance[model]["monthly_profit"]
            fig.add_trace(go.Bar(
                x=sorted_year_months,
                y=monthly_profit,
                name=f"{model} 月净收益",
                marker_color=colors.get(model, "#333"),
                text=[f"{v:.2f}" for v in monthly_profit],
                textposition='outside',
                textfont=dict(size=10),
            ))

    fig.update_layout(
        title="各型号月度净收益对比",
        xaxis_title="月份",
        yaxis_title="净收益（万欧元）",
        barmode='group',
        height=450,
        hovermode="x unified",
    )

    return fig


def plot_lcos_comparison(payback_data, sorted_year_months):
    fig = go.Figure()

    colors = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    for model_data in payback_data["models"]:
        model_name = model_data["name"]
        for row in model_data["rows"]:
            if "度电成本" in row["label"]:
                fig.add_trace(go.Scatter(
                    x=sorted_year_months,
                    y=row["values"],
                    mode='lines+markers',
                    name=f"{model_name} LCOS",
                    line=dict(width=2.5, color=colors.get(model_name, "#333")),
                    marker=dict(size=6),
                ))

    fig.update_layout(
        title="度电成本 (LCOS) 趋势对比",
        xaxis_title="月份",
        yaxis_title="度电成本 (€/kWh)",
        hovermode="x unified",
        height=400,
    )

    return fig


def plot_model_kpi_summary(model_finance, payback_data):
    models = []
    paybacks = []
    total_revenues = []
    colors_list = []

    color_map = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    for model_data in payback_data["models"]:
        model_name = model_data["name"]
        models.append(model_name)
        payback_val = model_finance[model_name].get("payback", 36)
        if payback_val is None:
            payback_val = 36
        paybacks.append(payback_val)
        total_revenues.append(model_data["total_row"]["value"])
        colors_list.append(color_map.get(model_name, "#333"))

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=models,
            y=paybacks,
            name="回收周期（月）",
            marker_color=colors_list,
            text=[f"{p:.1f}月" if p else "未回本" for p in paybacks],
            textposition='auto',
        ),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(
            x=models,
            y=total_revenues,
            mode='lines+markers',
            name="总收益（万欧元）",
            line=dict(width=3, color='#E91E63'),
            marker=dict(size=12, symbol='diamond'),
        ),
        secondary_y=True,
    )

    fig.update_layout(
        title="设备型号综合对比",
        height=400,
        hovermode="x",
    )

    fig.update_yaxes(title_text="回收周期（月）", secondary_y=False)
    fig.update_yaxes(title_text="总收益（万欧元）", secondary_y=True)

    return fig
