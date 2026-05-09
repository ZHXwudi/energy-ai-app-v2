EURO_CONSTRUCTION_COST_PER_UNIT = 0.498
EURO_DEVICE_COST_S1 = 1.443
EURO_DEVICE_COST_S2 = 1.742
EURO_DEVICE_COST_X3 = 6.035
EURO_BROKERAGE_RATE = 0.05
EURO_OPERATION_COST_PER_YEAR = 0.00124
EURO_INSURANCE_RATIO = 0.0015
EURO_ANNUAL_INTEREST_RATE = 0.04
DEFAULT_EXCHANGE_RATE = 7.8

EFFICIENCY = 0.95
DESIGN_CYCLES = 6000.0

DEVICE_SPECS = {
    "S1": {
        "power_per_unit": 100,
        "rated_per_unit": 225,
        "actual_per_unit": 235,
        "cost_lv": EURO_DEVICE_COST_S1,
        "cost_construction": EURO_CONSTRUCTION_COST_PER_UNIT,
    },
    "S2": {
        "power_per_unit": 130,
        "rated_per_unit": 261,
        "actual_per_unit": 271,
        "cost_lv": EURO_DEVICE_COST_S2,
        "cost_construction": EURO_CONSTRUCTION_COST_PER_UNIT,
    },
    "X3": {
        "power_per_unit": 418,
        "rated_per_unit": 836,
        "actual_per_unit": 876,
        "cost_lv": EURO_DEVICE_COST_X3,
        "cost_construction": EURO_CONSTRUCTION_COST_PER_UNIT,
    },
}

MODEL_LIST = ["S1", "S2", "X3"]

CYCLE_DECAY_FACTOR = 1.0 / 7000.0

EXCEL_FILES = [
    "电价透视表.xlsx",
    "充放电功率矩阵_S1.xlsx",
    "充放电功率矩阵_S2.xlsx",
    "充放电功率矩阵_X3.xlsx",
    "投资回收期表_月报.xlsx",
]
