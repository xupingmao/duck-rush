# -*- coding:utf-8 -*-
'''
Author: xupingmao
email: 578749341@qq.com
Date: 2024-07-30 02:13:22
LastEditors: xupingmao
LastEditTime: 2024-07-30 23:23:54
FilePath: /duck_rush/duck_rush/math-tools/calc-investment.py
Description: 描述
'''
# encoding=utf-8

import argparse
from datetime import datetime

def format_money(value=0, round_digits=2):
    value = round(value, round_digits)
    if value < 10000:
        return f"{value}"
    if value < 10000_0000:
        result = round(value/10000, round_digits)
        return f"{result}万"
    if value < 10000_0000_0000:
        result = round(value/10000_0000, round_digits)
        return f"{result}亿"
    return f"{value}"

THIS_YEAR = datetime.now().year

def main(savings=0, work_years=10, 
         income=100, 
         income_increase_rate=0.05,
         spend=20,
         spend_increase_rate=0.02, 
         investment_return_rate=0.1,
         start_year=THIS_YEAR,
         total_years=50):
    """投资计算器"""
    income_this_year = income
    round_digits = 2
    worked_years = 0
    spend_this_year = spend

    for year in range(total_years):
        abs_year = start_year + year
        worked_years += 1
        if worked_years > work_years:
            income_this_year = 0
        investment = savings * investment_return_rate
        savings = savings + income_this_year + investment - spend
        savings = round(savings, round_digits)

        print(f"第{year+1}年({abs_year}年)"
              f"\t年收入: {format_money(income_this_year):6s}"
              f"\t投资收入: {format_money(investment):6s}"
                f"\t消费支出: {format_money(spend_this_year):6s}"
                f"\t存款: {format_money(savings)}")
        income_this_year = income_this_year * (1+income_increase_rate)
        income_this_year = round(income_this_year, round_digits)
        spend_this_year = round(spend_this_year*(1+spend_increase_rate), round_digits)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--savings", default=0, type=int)
    parser.add_argument("--work-years", default=10, type=int)
    parser.add_argument("--income", default=100, type=float)
    parser.add_argument("--income-increase-rate", default=0.05, type=float)
    parser.add_argument("--spend", default=20, type=float)
    parser.add_argument("--spend-increase-rate", default=0.02, type=float)
    parser.add_argument("--investment-return-rate", default=0.1, type=float)
    parser.add_argument("--start-year", default=THIS_YEAR, type=int)
    parser.add_argument("--total-years", default=50, type=int)
    args = parser.parse_args()
    main(savings=args.savings, work_years=args.work_years,
         income=args.income, income_increase_rate=args.income_increase_rate,
         spend=args.spend, spend_increase_rate=args.spend_increase_rate,
         investment_return_rate=args.investment_return_rate,
         start_year=args.start_year, total_years=args.total_years)
