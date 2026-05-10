import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from core.config import MODEL_LIST


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


def plot_price_curves_for_month(price_rows, times, target_month):
    month_data = []
    for row in price_rows:
        date_str = row[0]
        prices = row[1:1 + len(times)]
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if date.strftime("%Y-%m") == target_month:
            month_data.append((date_str, prices))

    if not month_data:
        return None

    fig = go.Figure()
    for date_str, prices in month_data:
        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='lines',
            name=date_str,
            line=dict(width=1.5),
        ))

    fig.update_layout(
        title=f"{target_month} 每日电价曲线（共 {len(month_data)} 天）",
        xaxis_title="时刻",
        yaxis_title="电价 (€/kWh)",
        hovermode="x unified",
        height=500,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(r=150),
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


def plot_cumulative_cashflow_and_profit(model_finance, sorted_year_months):
    colors = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for model in MODEL_LIST:
        if model in model_finance:
            cum_cf = model_finance[model]["cum_cashflow"]
            monthly_profit = model_finance[model]["monthly_profit"]

            fig.add_trace(go.Scatter(
                x=sorted_year_months, y=cum_cf,
                mode='lines+markers',
                name=f"{model} 累计现金流",
                line=dict(width=3, color=colors.get(model, "#333")),
                marker=dict(size=6),
            ), secondary_y=False)

            fig.add_trace(go.Scatter(
                x=sorted_year_months, y=monthly_profit,
                mode='lines+markers',
                name=f"{model} 月度净收益",
                line=dict(width=2, color=colors.get(model, "#333"), dash='dot'),
                marker=dict(size=4, symbol='triangle-up'),
            ), secondary_y=True)

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

    fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5, secondary_y=False)

    fig.update_layout(
        title="累计现金流与月度净收益",
        hovermode="x unified",
        height=500,
        annotations=payback_annotations,
    )

    fig.update_yaxes(title_text="累计现金流（万欧元）", secondary_y=False)
    fig.update_yaxes(title_text="月度净收益（万欧元）", secondary_y=True)

    return fig


def plot_financial_indicators(payback_data, sorted_year_months, model_name):
    colors = {"S1": "#2196F3", "S2": "#4CAF50", "X3": "#FF9800"}

    model_rows = {}
    for model_data in payback_data["models"]:
        if model_data["name"] == model_name:
            for row in model_data["rows"]:
                model_rows[row["label"]] = row["values"]
            break

    indicator_keys = [
        ("平均购电电价 (€/kWh)", f"{model_name} 平均购电电价（€/kWh）"),
        ("平均放电电价 (€/kWh)", f"{model_name} 平均放电电价（€/kWh）"),
        ("表观电价差 (€/kWh)", f"{model_name} 表观电价差（€/kWh）"),
        ("度电成本 (€/kWh)", f"{model_name} 度电成本(3年折旧按月分摊)（€/kWh）"),
    ]

    fig = go.Figure()

    for display_name, full_label in indicator_keys:
        if full_label in model_rows:
            fig.add_trace(go.Scatter(
                x=sorted_year_months,
                y=model_rows[full_label],
                mode='lines+markers',
                name=display_name,
                line=dict(width=2),
                marker=dict(size=5),
            ))

    fig.update_layout(
        title=f"{model_name} 财务指标趋势",
        xaxis_title="月份",
        yaxis_title="€/kWh",
        hovermode="x unified",
        height=400,
    )

    return fig
