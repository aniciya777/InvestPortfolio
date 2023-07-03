from datetime import date
from os import path

import apimoex
import pandas as pd
import requests
from bokeh.layouts import column, row
from bokeh.models import Button, MultiChoice, Div, DateRangeSlider, RadioGroup, NumericInput, Switch, Paragraph, \
    GlobalImportedStyleSheet, ImportedStyleSheet, CustomJS
from bokeh.plotting import curdoc, figure
from pypfopt import risk_models, expected_returns, EfficientFrontier

from config import *
from fin_api import get_securities
from bokeh_pie_chart import PieChart


def event_callback_update_data(event):
    if not is_reset:
        calculate_portfolio()
        return
    clear_and_reset(None, None, None)
    global securities_list, date_from, date_to, secid_list, df
    securities_list = multi_choice_securities.value
    date_from, date_to = date_range_slider.value
    date_from = date.fromtimestamp(date_from / 1000)
    date_to = date.fromtimestamp(date_to / 1000)
    secid_list = [
        securities.loc[securities['SHORTNAME'] == security, 'SECID'].values[0]
        for security in securities_list]
    if not secid_list:
        results.text = f'<p><b>Внимание! Не выбраны ценные бумаги!</b></p>'
        return
    dfs = []
    try:
        for i, name in enumerate(secid_list):
            with requests.Session() as session:
                data = apimoex.get_board_history(
                    session,
                    name,
                    columns=('TRADEDATE', 'CLOSE'),
                    start=date_from.strftime('%Y-%m-%d'),
                    end=date_to.strftime('%Y-%m-%d'))
                df_temp = pd.DataFrame(data)
                df_temp.set_index('TRADEDATE', inplace=True)
                df_temp.rename(columns={'CLOSE': securities_list[i]}, inplace=True)
                dfs.append(df_temp)
        df = pd.concat(dfs, axis=1)
        table.text = '<p><b>Исходные данные:</b><br>' + \
                     df.\
                         to_html().\
                         replace('<td>NaN</td>', '<td class="error">—</td>').\
                         replace('<td>None</td>', '<td class="error">—</td>') + \
                     '</p>'
        if df.isna().values.any():
            raise Exception('В выбранном периоде есть пропуски в данных!')
        calculate_portfolio()
    except Exception as e:
        results.text = f'<p><b>Внимание! {e}</b></p>'


def clear_and_reset(attr, old, new):
    global is_reset
    is_reset = True
    clear(attr, old, new)


def clear(attr, old, new):
    results.text = ''
    table.visible = False
    result_portfolio.text = ''
    pie_chart.figure.visible = False


def method_selection_callback(attr, old, new):
    clear(attr, old, new)
    risk_target_input.visible = method_radio_group.active == 3
    returns_target_input.visible = method_radio_group.active == 4
    market_neutral_p.visible = market_neutral_switch.visible = method_radio_group.active in (2, 3, 4)


def calculate_portfolio():
    global is_reset
    risk_free_rate = risk_free_rate_input.value / 100
    risk_target = risk_target_input.value / 100
    returns_target = returns_target_input.value / 100
    market_neutral = market_neutral_switch.active

    mean_returns = expected_returns.mean_historical_return(df)
    covariances = risk_models.sample_cov(df)

    text = '<p><b>Среднегодовая (ежедневная) историческая доходность по исходным (ежедневным) ценам на активы:</b></p><ul>'
    for index, value in mean_returns.items():
        text += f'<li>{index}: <i>{round(value * 100, 2)} %</i></li>'
    text += '</ul>'
    text += '<p><b>Ковариационная матрица доходностей активов:</b></p>'
    text += covariances.to_html()
    results.text = text + '<hr>'

    ef = EfficientFrontier(mean_returns, covariances)
    match method_radio_group.active:
        case 0:
            weights = ef.max_sharpe(risk_free_rate)
        case 1:
            weights = ef.min_volatility()
        case 2:
            weights = ef.max_quadratic_utility(market_neutral=market_neutral)
        case 3:
            weights = ef.efficient_risk(risk_target, market_neutral=market_neutral)
        case 4:
            weights = ef.efficient_return(returns_target, market_neutral=market_neutral)
    ef.clean_weights()
    performance = ef.portfolio_performance(False, risk_free_rate)

    text = f'<b>Распределение активов в портфеле:</b><br><ul>'
    for index, value in weights.items():
        text += f'<li>{index}: <i>{round(value * 100, 2)} %</i></li>'
    text += '</ul><br><p><b>Оптимальный портфель активов:</b></p>'
    text += f'Ожидаемая доходность: <i>{round(performance[0] * 100, 2)} %</i><br>'
    text += f'Риск: <i>{round(performance[1] * 100, 2)} %</i><br>'
    text += f'Коэффициент Шарпа: <i>{round(performance[2], 2)}</i><br>'
    result_portfolio.text = text
    pie_chart.figure.visible = True
    pie_chart.data = weights
    table.visible = True
    is_reset = False


# Получение списка акций с Московской биржи
securities, options = get_securities()
multi_choice_securities = MultiChoice(
    value=DEFAULT_OPTIONS,
    options=options,
    title=f'Выберите компании для портфеля (не более {MAX_PORTFOLIO_SIZE}):',
    width=WIDTH,
    max_items=MAX_PORTFOLIO_SIZE,
)
multi_choice_securities.on_change('value', clear_and_reset)

today = date.today()
yesterday = today - pd.Timedelta(days=1)
date_range_slider = DateRangeSlider(
    value=(yesterday - DEFAULT_DATE_INTERVAL, yesterday),
    start=today - DATA_INTERVAL,
    end=today,
    title="Период для расчета доходности",
    width_policy='max',
)
date_range_slider.on_change('value', clear_and_reset)

risk_free_rate_input = NumericInput(
    value=DEFAULT_RISK_FREE_RATE,
    low=0,
    high=100,
    title="Безрисковая ставка, %",
    mode='float',
    width_policy='max')

method_radio_group = RadioGroup(
    labels=[
        'Максимизация коэффициента Шарпа',
        'Минимизация риска',
        'Максимизация квадратичной полезности',
        'Максимальная доходность при целевом риске',
        '«Портфель Марковица», минимизирующий волатильность для заданной целевой доходности'
    ],
    active=0)
method_radio_group.on_change('active', method_selection_callback)

risk_target_input = NumericInput(
    value=DEFAULT_RISK_TARGET,
    low=0,
    title="Целевой риск, %",
    mode='float',
    width_policy='max',
    visible=False)
risk_target_input.on_change('value', clear)

returns_target_input = NumericInput(
    value=DEFAULT_RETURNS_TARGET,
    low=0,
    title="Целевая доходность, %",
    mode='float',
    width_policy='max',
    visible=False)
returns_target_input.on_change('value', clear)

market_neutral_switch = Switch(
    active=False,
    visible=False)
market_neutral_switch.on_change('active', clear)
market_neutral_p = Paragraph(
    text='Портфель будет построен с нулевой чистой позицией (без учета рыночного риска)',
    width_policy='max',
    visible=False)

button = Button(label="РАССЧИТАТЬ", button_type="success", width_policy='max', height=50)
button.on_click(event_callback_update_data)

pie_chart = PieChart(
    data=dict(),
    title='Оптимальный портфель',
    width=WIDTH * 2 // 3,
    height=WIDTH // 2,
    visible=False,
    radius=0.6,
)

mean_returns_figure = figure(height=350, title="Fruit Counts",
           toolbar_location=None, tools="")

title = Div(text='''
<h1 style="text-align: center">
    Выбор оптимального портфеля акций
</h1>
<h2 style="text-align: center">
    Остапчук Анастасия Витальевна, гр. ПМИ-201
</h2>
<style>
    div {
        display: block !important;
    }
</style>
''', width=WIDTH)
title.css_classes = ['title']
results = Div(text='', width=WIDTH)
result_portfolio = Div(text='', width=WIDTH // 3)
table = Div(text='', width=WIDTH)

column = column(
    title,
    multi_choice_securities,
    date_range_slider,
    risk_free_rate_input,
    method_radio_group,
    risk_target_input,
    returns_target_input,
    row(market_neutral_switch, market_neutral_p),
    button,
    row(result_portfolio, pie_chart.figure),
    results,
    table,
)
css = GlobalImportedStyleSheet()
css.url = '@import url("InvestPortfolio/static/css/styles.css");'
css_table = ImportedStyleSheet()
css_table.url = 'InvestPortfolio/static/css/table.css'
table.stylesheets = [css_table]
column.stylesheets = [css]
results.stylesheets = [css_table]
curdoc().add_root(column)
curdoc().title = "Выбор акций"
column.css_classes = ['main']
is_reset = True
