from collections import defaultdict
from core.config import (DEVICE_SPECS, DESIGN_CYCLES, EURO_BROKERAGE_RATE,
                          EURO_OPERATION_COST_PER_YEAR, EURO_INSURANCE_RATIO,
                          EURO_ANNUAL_INTEREST_RATE, CYCLE_DECAY_FACTOR, MODEL_LIST)
from core.price_parser import prepare_price_rows
from core.optimizer import process_day_milp


def build_price_windows(dates, day_idx, times, price_by_date):
    prices_window = []
    for offset in range(3):
        idx = day_idx + offset
        if idx < len(dates):
            d = dates[idx]
            prices_window.extend([price_by_date[d].get(t, 0.0) for t in times])
        else:
            d = dates[-1]
            prices_window.extend([price_by_date[d].get(t, 0.0) for t in times])
    return prices_window


def run_single_model(model, dates, times, price_by_date, unit_count,
                     discharge_price_ratio, progress_callback=None):
    spec = DEVICE_SPECS[model]
    power_per_unit = spec["power_per_unit"]
    rated_per_unit = spec["rated_per_unit"]
    actual_per_unit = spec["actual_per_unit"]
    cost_lv = spec["cost_lv"]

    total_power = power_per_unit * unit_count
    initial_capacity = actual_per_unit * unit_count
    rated_capacity = rated_per_unit * unit_count

    model_marginal_cycle_cost = (cost_lv * 10000) / (DESIGN_CYCLES * rated_per_unit)

    current_capacity = initial_capacity
    prev_cycles = 0.0
    current_soc = 0.0

    monthly_stats = defaultdict(lambda: {
        "charge_energy": 0.0, "discharge_energy": 0.0,
        "revenue": 0.0, "cost": 0.0,
        "capacity_end": 0.0,
        "weighted_charge_price": 0.0, "weighted_discharge_price": 0.0,
        "total_charge_energy": 0.0, "total_discharge_energy": 0.0,
    })
    power_matrix_data = []
    all_year_months = set()

    total_days = len(dates)
    for day_idx, date in enumerate(dates):
        date_str = date.strftime("%Y-%m-%d")
        prices_window = build_price_windows(dates, day_idx, times, price_by_date)

        if day_idx == 0:
            capacity_today = current_capacity
        else:
            capacity_today = current_capacity - prev_cycles * CYCLE_DECAY_FACTOR * initial_capacity
            capacity_today = max(0, capacity_today)

        (power_seq, final_soc_day, charge_e, discharge_e,
         revenue, cost, profit,
         avg_charge, avg_discharge, avg_diff,
         threshold, actual_net_profit) = process_day_milp(
            date_str, times, prices_window, capacity_today, total_power,
            discharge_price_ratio, current_soc, model_marginal_cycle_cost
        )

        year_month = date.strftime("%Y-%m")
        all_year_months.add(year_month)
        stats = monthly_stats[year_month]
        stats["charge_energy"] += charge_e
        stats["discharge_energy"] += discharge_e
        stats["revenue"] += revenue
        stats["cost"] += cost
        stats["capacity_end"] = capacity_today
        if charge_e > 0:
            stats["weighted_charge_price"] += avg_charge * charge_e
            stats["total_charge_energy"] += charge_e
        if discharge_e > 0:
            stats["weighted_discharge_price"] += avg_discharge * discharge_e
            stats["total_discharge_energy"] += discharge_e

        cycle_today = min(charge_e, discharge_e) / capacity_today if capacity_today > 0 else 0.0

        power_matrix_data.append([
            date_str, *power_seq,
            capacity_today, final_soc_day,
            charge_e, discharge_e, revenue, cost, profit, cycle_today,
            avg_charge, avg_discharge, avg_diff, threshold, actual_net_profit,
        ])

        current_capacity = capacity_today
        prev_cycles = cycle_today
        current_soc = final_soc_day

        if progress_callback and total_days > 0:
            progress_callback(model, day_idx + 1, total_days)

    return {
        "rated_capacity": rated_capacity,
        "initial_capacity": initial_capacity,
        "monthly_stats": monthly_stats,
        "power_matrix_data": power_matrix_data,
        "all_year_months": all_year_months,
    }


def run_all_models(price_by_date, unit_count, discharge_price_ratio,
                   exchange_rate, progress_callback=None):
    times = sorted({t for d in price_by_date for t in price_by_date[d]})
    if not times:
        times = [f"{h:02d}:00:00" for h in range(24)]

    dates, price_rows, price_headers = prepare_price_rows(price_by_date, times)

    model_results = {}
    all_year_months = set()

    for model in MODEL_LIST:
        result = run_single_model(model, dates, times, price_by_date,
                                  unit_count, discharge_price_ratio,
                                  progress_callback)
        model_results[model] = result
        all_year_months |= result["all_year_months"]

    sorted_year_months = sorted(all_year_months) if all_year_months else ["2026-01"]

    power_matrix_headers = (
        ["日期"] + times +
        ["充电容量(kWh)", "剩余电量(kWh)", "当天充电量(kWh)", "当天放电量(kWh)",
         "发电收入(€)", "购电成本(€)", "收益(€)", "循环次数(次)",
         "平均购电电价(€/kWh)", "平均放电电价(€/kWh)", "表观电价差(€/kWh)",
         "折旧及损耗阈值(€/kWh)", "实际度电净利(€/kWh)"]
    )

    return {
        "dates": dates,
        "price_rows": price_rows,
        "price_headers": price_headers,
        "times": times,
        "model_results": model_results,
        "sorted_year_months": sorted_year_months,
        "power_matrix_headers": power_matrix_headers,
    }


def calculate_payback_period(cum_cashflows):
    for i in range(len(cum_cashflows) - 1):
        if cum_cashflows[i] <= 0 < cum_cashflows[i + 1]:
            neg_value = cum_cashflows[i]
            pos_value = cum_cashflows[i + 1]
            month = i + 1
            payback = month + abs(neg_value) / (pos_value - neg_value)
            return round(payback, 2)
    return None


def calculate_finance(model_results, sorted_year_months, unit_count, exchange_rate):
    model_finance = {}
    initial_capacity_dict = {}
    rated_capacity_dict = {}

    for model in MODEL_LIST:
        result = model_results[model]
        rated_capacity_dict[model] = result["rated_capacity"]
        initial_capacity_dict[model] = result["initial_capacity"]

    for model in MODEL_LIST:
        result = model_results[model]
        spec = DEVICE_SPECS[model]
        cost_lv = spec["cost_lv"]
        cost_construction = spec["cost_construction"]
        rated_cap = rated_capacity_dict[model]

        station_invest = unit_count * cost_lv
        construction_invest = unit_count * cost_construction
        brokerage_fee = rated_cap * EURO_BROKERAGE_RATE / 10.0
        total_initial_invest = (station_invest + construction_invest + brokerage_fee) * 1.3

        annual_operation_cost = unit_count * 20 * EURO_OPERATION_COST_PER_YEAR
        invest_no_tax_yr1 = (station_invest / 1.13 + construction_invest + brokerage_fee) * 1.3
        annual_insurance_cost = EURO_INSURANCE_RATIO * invest_no_tax_yr1

        monthly_operation = annual_operation_cost / 12.0
        monthly_insurance = annual_insurance_cost / 12.0

        num_months = len(sorted_year_months)
        monthly_stats = result["monthly_stats"]

        initial_invest_row = [total_initial_invest] + [0.0] * (num_months - 1)
        operation_row = [monthly_operation] * num_months
        insurance_row = [monthly_insurance] * num_months

        monthly_revenue = [monthly_stats[ym]["revenue"] / 10000.0 for ym in sorted_year_months]
        monthly_cost = [monthly_stats[ym]["cost"] / 10000.0 for ym in sorted_year_months]
        monthly_profit = [rev - cost for rev, cost in zip(monthly_revenue, monthly_cost)]
        monthly_tax = [rev * 3 / 10000.0 for rev in monthly_revenue]

        interest_row = []
        net_cashflow = []
        cum_cashflow = []
        running = 0.0
        current_year_interest = 0.0

        for i in range(num_months):
            ym = sorted_year_months[i]
            is_first_month = (ym.endswith("-01") or i == 0)

            cash_out_excl = initial_invest_row[i] + operation_row[i] + insurance_row[i] + monthly_tax[i]
            net_excl = monthly_profit[i] - cash_out_excl
            cum_excl = running + net_excl

            if is_first_month:
                if cum_excl < 0:
                    current_year_interest = ((-EURO_ANNUAL_INTEREST_RATE * cum_excl / 12.0) /
                                             (1.0 - EURO_ANNUAL_INTEREST_RATE / 12.0)) / exchange_rate
                else:
                    current_year_interest = 0.0

            interest_row.append(current_year_interest)
            cash_out = cash_out_excl + current_year_interest
            monthly_cash_out = cash_out
            net = monthly_profit[i] - cash_out
            net_cashflow.append(net)
            running += net
            cum_cashflow.append(running)

        finance_rows = [
            ("初始投资（万欧元）", initial_invest_row),
            ("运营费用（万欧元）", operation_row),
            ("保险费用（万欧元）", insurance_row),
            ("利息（万欧元）", interest_row),
            ("税金及附加（万欧元）", monthly_tax),
            ("现金流出（万欧元）", [initial_invest_row[i] + operation_row[i] + insurance_row[i] + monthly_tax[i] + interest_row[i] for i in range(num_months)]),
            ("月度净收益（万欧元）", monthly_profit),
        ]

        payback = calculate_payback_period(cum_cashflow)

        model_finance[model] = {
            "finance_rows": finance_rows,
            "cum_cashflow_row": ("累计现金流（万欧元）", cum_cashflow),
            "payback": payback,
            "initial_invest_total": total_initial_invest,
            "operation_row": operation_row,
            "insurance_row": insurance_row,
            "interest_row": interest_row,
            "monthly_profit": monthly_profit,
            "net_cashflow": net_cashflow,
            "cum_cashflow": cum_cashflow,
        }

    payback_data = {
        "sorted_year_months": sorted_year_months,
        "models": [],
        "model_finance": model_finance,
    }

    row_suffixes = [
        ("储能容量（kWh）", lambda m, ym: rated_capacity_dict[m]),
        ("电池容量比", lambda m, ym: (model_results[m]["monthly_stats"][ym]["capacity_end"] / initial_capacity_dict[m])
         if initial_capacity_dict[m] > 0 else 0.0),
        ("充电量（万度）", lambda m, ym: model_results[m]["monthly_stats"][ym]["charge_energy"] / 10000.0),
        ("放电量（万度）", lambda m, ym: model_results[m]["monthly_stats"][ym]["discharge_energy"] / 10000.0),
        ("发电收入（万欧元）", lambda m, ym: model_results[m]["monthly_stats"][ym]["revenue"] / 10000.0),
        ("购电成本（万欧元）", lambda m, ym: model_results[m]["monthly_stats"][ym]["cost"] / 10000.0),
        ("收益（万欧元）", lambda m, ym: (model_results[m]["monthly_stats"][ym]["revenue"] - model_results[m]["monthly_stats"][ym]["cost"]) / 10000.0),
        ("平均购电电价（€/kWh）", lambda m, ym: (model_results[m]["monthly_stats"][ym]["weighted_charge_price"] / model_results[m]["monthly_stats"][ym]["total_charge_energy"])
         if model_results[m]["monthly_stats"][ym]["total_charge_energy"] > 0 else 0.0),
        ("平均放电电价（€/kWh）", lambda m, ym: (model_results[m]["monthly_stats"][ym]["weighted_discharge_price"] / model_results[m]["monthly_stats"][ym]["total_discharge_energy"])
         if model_results[m]["monthly_stats"][ym]["total_discharge_energy"] > 0 else 0.0),
        ("表观电价差（€/kWh）", lambda m, ym: (
            (model_results[m]["monthly_stats"][ym]["weighted_discharge_price"] / model_results[m]["monthly_stats"][ym]["total_discharge_energy"])
            if model_results[m]["monthly_stats"][ym]["total_discharge_energy"] > 0 else 0.0
        ) - (
            (model_results[m]["monthly_stats"][ym]["weighted_charge_price"] / model_results[m]["monthly_stats"][ym]["total_charge_energy"])
            if model_results[m]["monthly_stats"][ym]["total_charge_energy"] > 0 else 0.0
        )),
    ]

    for model in MODEL_LIST:
        model_rows = []
        for suffix, value_func in row_suffixes:
            label = f"{model} {suffix}"
            values = [value_func(model, ym) for ym in sorted_year_months]
            model_rows.append({"label": label, "values": values})

        monthly_lcos_row = []
        finance_info = model_finance[model]
        monthly_amortized_capex = finance_info["initial_invest_total"] / 36.0

        for i, ym in enumerate(sorted_year_months):
            monthly_opex = finance_info["operation_row"][i] + finance_info["insurance_row"][i] + finance_info["interest_row"][i]
            monthly_cost_eur = (monthly_amortized_capex + monthly_opex) * 10000
            monthly_discharge = model_results[model]["monthly_stats"][ym]["discharge_energy"]
            lcos = monthly_cost_eur / monthly_discharge if monthly_discharge > 0 else 0.0
            monthly_lcos_row.append(lcos)

        model_rows.append({"label": f"{model} 度电成本(3年折旧按月分摊)（€/kWh）", "values": monthly_lcos_row})

        total_profit = sum(
            (model_results[model]["monthly_stats"][ym]["revenue"] - model_results[model]["monthly_stats"][ym]["cost"]) / 10000.0
            for ym in sorted_year_months
        )
        total_row = {"label": f"{model} 总收益（万欧元）", "value": total_profit}
        payback_data["models"].append({
            "name": model,
            "rows": model_rows,
            "total_row": total_row,
        })

    return model_finance, payback_data
