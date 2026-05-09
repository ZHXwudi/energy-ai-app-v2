import pulp
from core.config import EFFICIENCY


def process_day_milp(date_str, times, prices_window, capacity_kwh, max_power_kw,
                     discharge_price_ratio, init_soc_kwh, marginal_cycle_cost):
    init_soc_kwh = min(max(0.0, float(init_soc_kwh)), float(capacity_kwh))
    T = len(prices_window)

    prob = pulp.LpProblem(f"MILP_Storage_{date_str}", pulp.LpMaximize)

    P_ch = pulp.LpVariable.dicts("P_ch", range(T), lowBound=0, upBound=max_power_kw)
    P_dis = pulp.LpVariable.dicts("P_dis", range(T), lowBound=0, upBound=max_power_kw)
    SOC = pulp.LpVariable.dicts("SOC", range(T + 1), lowBound=0, upBound=capacity_kwh)
    Is_Ch = pulp.LpVariable.dicts("Is_Ch", range(T), cat=pulp.LpBinary)

    prob += pulp.lpSum([
        P_dis[t] * prices_window[t] * discharge_price_ratio -
        P_ch[t] * prices_window[t] -
        P_dis[t] * marginal_cycle_cost
        for t in range(T)
    ])

    prob += SOC[0] == init_soc_kwh
    for t in range(T):
        prob += SOC[t + 1] == SOC[t] + P_ch[t] * EFFICIENCY - (P_dis[t] / EFFICIENCY)
        prob += P_ch[t] <= max_power_kw * Is_Ch[t]
        prob += P_dis[t] <= max_power_kw * (1 - Is_Ch[t])

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != pulp.LpStatusOptimal:
        return ([0.0] * 24, init_soc_kwh, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    final_power = [0.0] * 24
    total_charge = 0.0
    total_discharge = 0.0
    total_revenue = 0.0
    total_cost = 0.0
    charge_weighted = []
    discharge_weighted = []

    for t in range(24):
        ch = P_ch[t].varValue if P_ch[t].varValue is not None else 0.0
        dis = P_dis[t].varValue if P_dis[t].varValue is not None else 0.0
        if dis > 1e-4:
            final_power[t] = dis
            total_discharge += dis
            total_revenue += dis * prices_window[t] * discharge_price_ratio
            discharge_weighted.append((prices_window[t], dis))
        elif ch > 1e-4:
            final_power[t] = -ch
            total_charge += ch
            total_cost += ch * prices_window[t]
            charge_weighted.append((prices_window[t], ch))

    current_soc = SOC[24].varValue if SOC[24].varValue is not None else 0.0
    avg_charge = sum(p * e for p, e in charge_weighted) / total_charge if total_charge > 0 else 0.0
    avg_discharge = sum(p * e for p, e in discharge_weighted) / total_discharge if total_discharge > 0 else 0.0
    avg_diff = avg_discharge - avg_charge
    profit = total_revenue - total_cost

    min_price_today = min(prices_window[:24])
    base_price = avg_charge if total_charge > 0 else min_price_today
    efficiency_loss_cost = base_price * (1.0 / (EFFICIENCY * EFFICIENCY) - 1.0)
    threshold = marginal_cycle_cost + efficiency_loss_cost
    actual_net_profit = profit / total_discharge if total_discharge > 0 else 0.0

    return (final_power, current_soc, total_charge, total_discharge,
            total_revenue, total_cost, profit,
            avg_charge, avg_discharge, avg_diff, threshold, actual_net_profit)
