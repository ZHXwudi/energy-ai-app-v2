import csv
import os
from collections import defaultdict
from core.utils import safe_str, safe_float, try_parse_date, try_parse_time, is_hourly


def parse_price_csv(file_path):
    price_by_date = defaultdict(dict)
    times_set = set()

    if not os.path.exists(file_path):
        return {}, set()

    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            first_line = f.readline()
            f.seek(0)
            dialect = csv.Sniffer().sniff(first_line)
            delimiter = dialect.delimiter
            reader = csv.DictReader(f, delimiter=delimiter)
            if not reader.fieldnames:
                return {}, set()

            fieldnames_lower = [fn.lower().strip() for fn in reader.fieldnames]
            date_col = None
            time_col = None
            price_col = None

            for idx, col in enumerate(fieldnames_lower):
                if '日期' in col or 'date' in col:
                    date_col = reader.fieldnames[idx]
                elif '时间' in col or 'time' in col:
                    time_col = reader.fieldnames[idx]
                elif '电价' in col or 'price' in col:
                    price_col = reader.fieldnames[idx]

            if not date_col or not time_col or not price_col:
                return {}, set()

            for row in reader:
                date_str = safe_str(row.get(date_col, ''))
                time_str = safe_str(row.get(time_col, ''))
                price_str = safe_str(row.get(price_col, ''))
                if not date_str or not time_str or not price_str:
                    continue
                date = try_parse_date(date_str)
                if not date:
                    continue
                time_fmt = try_parse_time(time_str)
                if not is_hourly(time_fmt):
                    continue
                price_mwh = safe_float(price_str)
                price_kwh = price_mwh / 1000.0
                price_by_date[date][time_fmt] = price_kwh
                times_set.add(time_fmt)
    except Exception:
        return {}, set()

    return price_by_date, times_set


def get_daily_top_pairs(prices, discharge_price_ratio, max_pairs=12):
    n = len(prices)
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            spread = prices[j] * discharge_price_ratio - prices[i]
            all_pairs.append((spread, i, j))
    all_pairs.sort(key=lambda x: x[0], reverse=True)
    used_hours = set()
    top_pairs = []
    for spread, ch, dis in all_pairs:
        if ch in used_hours or dis in used_hours:
            continue
        top_pairs.append((spread, ch, dis))
        used_hours.add(ch)
        used_hours.add(dis)
        if len(top_pairs) >= max_pairs:
            break
    return top_pairs


def prepare_price_rows(price_by_date, times):
    dates = sorted(price_by_date.keys())
    price_rows = []
    for date in dates:
        row = [date.strftime("%Y-%m-%d")] + [price_by_date[date].get(t, 0.0) for t in times]
        price_rows.append(row)
    price_headers = ["日期"] + times
    return dates, price_rows, price_headers
