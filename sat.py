api_key = 'test'
api_secret = 'test'
mail_pass = 'test'
mail_host = 'imap.gmail.com'
mail_login = 'test'

import imaplib
import email
import numpy as np
import time
from binance.client import Client
client = Client(api_key, api_secret)


def buy_func(what_to_buy, what_for, share=0.99):
    ticker = what_to_buy + what_for
    balances_atm = client.get_account()['balances']
    test = client.get_symbol_info(ticker)

    price_atm = {i['symbol']: i['price'] for i in client.get_symbol_ticker() if i['symbol'] == ticker}

    available = {i['asset']: i['free'] for i in balances_atm if i['asset'] in [what_to_buy, what_for]}
    max_amount_to_buy = np.format_float_positional((float(available[what_for]) / float(price_atm[ticker])) * share)

    min_notional = {i['filterType']: i['minNotional'] for i in test['filters'] if i['filterType'] == 'MIN_NOTIONAL'}
    min_amount_to_buy = np.format_float_positional(float(min_notional['MIN_NOTIONAL']) / float(price_atm[ticker]))

    if float(max_amount_to_buy) > float(min_amount_to_buy):
        min_lot_size = {i['filterType']: i['minQty'] for i in test['filters'] if i['filterType'] == 'LOT_SIZE'}
        min_lot_size = np.format_float_positional(float(min_lot_size['LOT_SIZE']))
        final_amount_to_buy = str(max_amount_to_buy)[0:len(min_lot_size.split('.')[1]) +
                                                       len(str(max_amount_to_buy).split('.')[0]) + 1]
        return final_amount_to_buy
    else:
        print('amount less than minimum order!')



def sell_func(what_to_sell, what_for, share=0.99):
    ticker = what_to_sell + what_for
    balances_atm = client.get_account()['balances']
    test = client.get_symbol_info(ticker)

    price_atm = {i['symbol']: i['price'] for i in client.get_symbol_ticker() if i['symbol'] == ticker}
    available = {i['asset']: i['free'] for i in balances_atm if i['asset'] in [what_to_sell, what_for]}
    max_amount_to_sell = np.format_float_positional(float(available[what_to_sell]) * share)

    min_notional = {i['filterType']: i['minNotional'] for i in test['filters'] if i['filterType'] == 'MIN_NOTIONAL'}
    min_amount_to_sell = np.format_float_positional(float(min_notional['MIN_NOTIONAL']) / float(price_atm[ticker]))

    if float(max_amount_to_sell) > float(min_amount_to_sell):
        min_lot_size = {i['filterType']: i['minQty'] for i in test['filters'] if i['filterType'] == 'LOT_SIZE'}
        min_lot_size = np.format_float_positional(float(min_lot_size['LOT_SIZE']))
        final_amount_to_sell = str(max_amount_to_sell)[0:len(min_lot_size.split('.')[1]) +
                                                         len(str(max_amount_to_sell).split('.')[0]) + 1]
        return final_amount_to_sell
    else:
        print('amount less than minimum order!')



#connector = imaplib.IMAP4_SSL(mail_host)
#connector.login(mail_login, mail_pass)



## ОСНОВНОЙ ЦИКЛ
while True:
    time.sleep(10)
    connector = imaplib.IMAP4_SSL(mail_host)
    connector.login(mail_login, mail_pass)
    connector.select("TradingView_Alerts")
    resp, items = connector.search(None, "ALL")

    for emailid in items[0].split():
        resp, data = connector.fetch(emailid, '(RFC822)')
        mail = email.message_from_bytes(data[0][1])
        print(mail['Subject'], mail['Date'])
        if 'Sell' in mail['Subject']:

            what_to_sell = 'BTC'
            what_for = 'USDT'
            ## ПОСТАВИМ ОРДЕР НА ПРОДАЖУ
            try:
                order_sell = client.create_order(symbol=what_to_sell + what_for,
                                                 side=Client.SIDE_SELL,
                                                 type=Client.ORDER_TYPE_MARKET,
                                                 newOrderRespType='FULL',
                                                 quantity=sell_func(what_to_sell, what_for))
                print('sell order', '\n', order_sell['symbol'], order_sell['fills'])
            except:
                print('error ... probably not enough money')

        elif 'Buy' in mail['Subject']:
            what_to_buy = 'BTC'
            what_for = 'USDT'
            ## ПОСТАВИМ ОРДЕР НА ПОКУПКУ
            try:
                order_buy = client.create_order(symbol=what_to_buy + what_for,
                                                side=Client.SIDE_BUY,
                                                type=Client.ORDER_TYPE_MARKET,
                                                newOrderRespType='FULL',
                                                quantity=buy_func(what_to_buy, what_for))
                print('buy order', '\n', order_buy['symbol'], order_buy['fills'])
            except:
                print('error ... probably not enough money')
        else:
            print('Unknow email')
        print('Deleting email')
        connector.store(emailid, '+FLAGS', '\\Deleted')
        connector.expunge()
    print('done')
    connector.close()
    connector.logout()


#connector.close()
#connector.logout()
