from datetime import date, timedelta

import apimoex
import pandas as pd
import requests
from bokeh.layouts import column
from bokeh.models import Button, MultiChoice, Div, DateRangeSlider, DataTable, TableColumn, DateFormatter, \
    ColumnDataSource, RadioGroup
from bokeh.plotting import curdoc
from pypfopt import risk_models, expected_returns, EfficientFrontier

WIDTH = 800
MIN_START_BALANCE = 1
MAX_START_BALANCE = 1_000_000
DEFAULT_START_BALANCE = 10_000
DEFAULT_OPTIONS = ['Yandex clA', 'Сбербанк', 'МТС-ао', 'ВТБ ао']
MAX_PORTFOLIO_SIZE = 10
DATA_INTERVAL = timedelta(days=365 * 10)
DEFAULT_DATE_INTERVAL = timedelta(days=90)


def event_callback_update_data(event):
    if not is_reset:
        calculate_portfolio()
        return
    global securities_list, date_from, date_to, secid_list, df
    securities_list = multi_choice_securities.value
    date_from, date_to = date_range_slider.value
    date_from = date.fromtimestamp(date_from / 1000)
    date_to = date.fromtimestamp(date_to / 1000)
    secid_list = [
        securities.loc[securities['SHORTNAME'] == security, 'SECID'].values[0]
        for security in securities_list]
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
        table.text = '<p><b>Исходные данные:</b><br>' + df.to_html() + '</p>'

        dtable.columns = [
            TableColumn(field="Date", title="Date", formatter=DateFormatter()),
            *(TableColumn(field=security, title=security) for security in securities_list)
        ]
        dtable.source = ColumnDataSource({
            'Date': list(df.index),
            **{security: df[security] for security in securities_list}
        })
        if df.isna().values.any():
            raise Exception('В выбранном периоде есть пропуски в данных!')
        calculate_portfolio()
    except Exception as e:
        results.text = '<p><b>Внимание! В выбранном периоде есть пропуски в данных!</b></p>'
        return


def clear(attr, old, new):
    global is_reset
    is_reset = True
    results.text = ''
    table.text = ''


def calculate_portfolio():
    text = '<p><b>Среднегодовая (ежедневная) историческая доходность по исходным (ежедневным) ценам на активы:</b><br><ul>'
    mean_returns = expected_returns.mean_historical_return(df)
    for index, value in mean_returns.items():
        text += f'<li>{index}: <i>{round(value * 100, 2)} %</i></li>'
    text += '</ul></p>'
    covariances = risk_models.sample_cov(df)
    text += '<p><b>Ковариационная матрица доходностей активов:</b><br>'
    text += covariances.to_html()
    text += '</p>'
    text += '<p><b>Оптимальный портфель активов:</b><br>'
    ef = EfficientFrontier(mean_returns, covariances)
    match method_radio_group.active:
        case 0:
            weights = ef.max_sharpe()
        case 1:
            weights = ef.min_volatility()
        case 2:
            weights = ef.max_quadratic_utility()
    ef.clean_weights()
    text += f'Ожидаемая доходность: <i>{round(ef.portfolio_performance()[0] * 100, 2)} %</i><br>'
    text += f'Риск: <i>{round(ef.portfolio_performance()[1] * 100, 2)} %</i><br>'
    text += f'Коэффициент Шарпа: <i>{round(ef.portfolio_performance()[2], 2)}</i><br>'
    text += f'<b>Распределение активов в портфеле:</b><br>'
    for index, value in weights.items():
        text += f'<li>{index}: <i>{round(value * 100, 2)} %</i></li>'
    text += '</ul></p>'
    text += '<hr>'
    results.text = text
    is_reset = False


# Получение списка акций с Московской биржи
try:
    with requests.Session() as session:
        iss = apimoex.ISSClient(session,
                                'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json',
                                {'securities.columns': 'SECID,SHORTNAME'})
        securities = pd.DataFrame(iss.get()['securities'])
    options = list(securities['SHORTNAME'])
except Exception:
    options = []
multi_choice_securities = MultiChoice(
    value=DEFAULT_OPTIONS,
    options=options,
    title=f'Выберите компании для портфеля (не более {MAX_PORTFOLIO_SIZE}):',
    width_policy='max',
    max_items=MAX_PORTFOLIO_SIZE,
)
multi_choice_securities.on_change('value', clear)

today = date.today()
yesterday = today - pd.Timedelta(days=1)
date_range_slider = DateRangeSlider(
    value=(yesterday - DEFAULT_DATE_INTERVAL, yesterday),
    start=today - DATA_INTERVAL,
    end=today,
    title="Период для расчета доходности",
    width_policy='max',
)
date_range_slider.on_change('value', clear)
method_radio_group = RadioGroup(
    labels=['Максимизация коэффициента Шарпа', 'Минимизация риска', 'Максимизация квадратичной полезности'],
    active=0)
button = Button(label="РАССЧИТАТЬ (МАКСИМИЗАЦИЯ КОЭФФИЦИЕНТА ШАРПА)", button_type="success")
button.on_click(event_callback_update_data)

title = Div(text='''
<h1 style="text-align: center">
    Выбор оптимального портфеля акций
</h1>
<h2>
    Остапчук Анастасия Витальевна, гр. ПМИ-201
</h2>
''')
results = Div(text='')
table = Div(text='')
dtable = DataTable(width_policy='max')
curdoc().add_root(column(
    title,
    multi_choice_securities,
    date_range_slider,
    method_radio_group,
    button,
    results,
    table,
    # dtable,
))
curdoc().title = "Выбор акций"
is_reset = True
