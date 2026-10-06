"""Savings and profit estimate.

Computed in code from the visitor's own numbers and the service assumptions,
never by the language model, so every figure is reproducible.
"""

from .intake import CURRENCIES
from .services import SERVICES

WEEKS_PER_MONTH = 52 / 12


def money(amount, currency):
    symbol = CURRENCIES.get(currency, currency + " ")
    amount = round(amount)
    if currency == "INR":
        # Indian grouping: 12,34,567
        s = str(abs(amount))
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            s = ",".join(groups) + "," + tail
        return f"{'-' if amount < 0 else ''}{symbol}{s}"
    return f"{'-' if amount < 0 else ''}{symbol}{abs(amount):,}"


def estimate(intake):
    svc = SERVICES[intake["service"]]
    cur = intake["currency"]

    hours_saved = intake["hours_per_week"] * WEEKS_PER_MONTH * svc["automation_share"]
    labour_saving = hours_saved * intake["hourly_cost"]

    customers_now = intake["monthly_inquiries"] * intake["conversion_pct"] / 100
    extra_customers = customers_now * svc["conversion_uplift"]
    extra_revenue = extra_customers * intake["avg_order_value"]
    extra_profit = extra_revenue * intake["margin_pct"] / 100

    monthly_gain = labour_saving + extra_profit
    result = {
        "currency": cur,
        "hours_saved_month": round(hours_saved),
        "labour_saving_month": round(labour_saving),
        "extra_customers_month": round(extra_customers, 1),
        "extra_revenue_month": round(extra_revenue),
        "extra_profit_month": round(extra_profit),
        "monthly_gain": round(monthly_gain),
        "yearly_gain": round(monthly_gain * 12),
        "assumptions": [
            f"The engine takes over {round(svc['automation_share'] * 100)}% of the {intake['hours_per_week']:g} hours a week your team spends on this work today.",
            f"Team time is valued at {money(intake['hourly_cost'], cur)} an hour.",
        ],
    }
    if svc["conversion_uplift"]:
        result["assumptions"].append(
            f"Faster replies and automatic follow-ups lift your {intake['conversion_pct']:g}% conversion by "
            f"{round(svc['conversion_uplift'] * 100)}% (relative), at a {intake['margin_pct']:g}% profit margin "
            f"on {money(intake['avg_order_value'], cur)} per order."
        )
    result["display"] = {
        "hours_saved_month": f"{result['hours_saved_month']:,} hours",
        "labour_saving_month": money(labour_saving, cur),
        "extra_revenue_month": money(extra_revenue, cur),
        "extra_profit_month": money(extra_profit, cur),
        "monthly_gain": money(monthly_gain, cur),
        "yearly_gain": money(monthly_gain * 12, cur),
    }
    return result
