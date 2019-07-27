api_key = 'test'
api_secret = 'test'
mail_pass = 'test'
mail_host = 'imap.gmail.com'
mail_login = 'test'
telegram_bot_token = 'test'
telegram_bot_chatID = 'test'
to_trade = ['BTC','ETH','XRP','EOS','BSV','ADA']






import requests
import imaplib
import email
import numpy as np
import time
import datetime as dt
from binance.client import Client
client = Client(api_key, api_secret)

def smart_split(to_trade):
    balances_full = client.get_account()['balances']
    balances_val = [i for i in balances_full if float(i['free'])>0]
    balances_actual = {i['asset']:i['free'] for i in balances_val}
    prices = {i['symbol'][:-4]:i['price'] for i in client.get_symbol_ticker() if i['symbol'] in [j+'USDT' for j in balances_actual.keys()]}
    balances_actual_usd = {i:float(balances_actual[i])*float(prices[i]) if i in prices.keys() else float(balances_actual[i]) for i in balances_actual.keys()}

    to_trade_balances_usd = [balances_actual_usd[i] for i in balances_actual_usd.keys() if i in to_trade+['USDT']]
    balance_benchmark = sum(to_trade_balances_usd)/len(to_trade)*0.1
    cur_in_actin = {i:balances_actual_usd[i] for i in balances_actual_usd if (i in to_trade) & (balances_actual_usd[i]>balance_benchmark)}
    use_next_deal = balances_actual_usd['USDT']/(len(to_trade) - len(cur_in_actin))
    return use_next_deal


def buy_func(what_to_buy, what_for, share):
    ticker = what_to_buy + what_for
    ticker_info = client.get_symbol_info(symbol=ticker)
    price_atm = client.get_symbol_ticker(symbol=ticker)
    min_notional = {i['filterType']: i['minNotional'] for i in ticker_info['filters'] if i['filterType'] == 'MIN_NOTIONAL'}

    max_amount_to_buy = np.format_float_positional((smart_split(to_trade)/float(price_atm['price']))*share)
    min_amount_to_buy = np.format_float_positional(float(min_notional['MIN_NOTIONAL']) / float(price_atm['price']))

    if float(max_amount_to_buy) > float(min_amount_to_buy):
        min_lot_size = {i['filterType']: i['minQty'] for i in ticker_info['filters'] if i['filterType'] == 'LOT_SIZE'}
        min_lot_size = np.format_float_positional(float(min_lot_size['LOT_SIZE']))
        final_amount_to_buy = str(max_amount_to_buy)[0:len(min_lot_size.split('.')[1]) +
                                                       len(str(max_amount_to_buy).split('.')[0]) + 1]
        return final_amount_to_buy
    else:
        print('amount less than minimum order!', flush=True)


def execute_buy(what_to_buy, what_for, share):
    ## ПОСТАВИМ ОРДЕР НА ПОКУПКУ
    try:
        order_buy = client.create_order(symbol=what_to_buy + what_for,
                                        side=Client.SIDE_BUY,
                                        type=Client.ORDER_TYPE_MARKET,
                                        newOrderRespType='FULL',
                                        quantity=buy_func(what_to_buy, what_for, share))
        print('buy order', '\n', order_buy['symbol'], order_buy['fills'],  flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'buy order executed :)) ' +\
                                       str(order_buy['symbol']) + ' '+\
                                       str(order_buy['fills']) + ' '+\
                                       str(float(order_buy['fills'][0]['price'])*float(order_buy['fills'][0]['qty'])))
    except:
        print('error ... probably not enough money', flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'ERROR executing buy order!!')
    finally:
        print( tg_tmp['result']['chat'], '\n', tg_tmp['ok'],' Telegram message sent!')


def sell_func(what_to_sell, what_for, share):
    ticker = what_to_sell + what_for
    balance_atm = client.get_asset_balance(asset=what_to_sell)
    price_atm = client.get_symbol_ticker(symbol=ticker)
    ticker_info = client.get_symbol_info(ticker)
    min_notional = {i['filterType']:i['minNotional'] for i in ticker_info['filters'] if i['filterType']=='MIN_NOTIONAL'}

    max_amount_to_sell = np.format_float_positional(float(balance_atm['free'])*share)
    min_amount_to_sell = np.format_float_positional(float(min_notional['MIN_NOTIONAL'])/float(price_atm['price']))

    if float(max_amount_to_sell)>float(min_amount_to_sell):
        min_lot_size = {i['filterType']:i['minQty'] for i in ticker_info['filters'] if i['filterType']=='LOT_SIZE'}
        min_lot_size = np.format_float_positional(float(min_lot_size['LOT_SIZE']))
        final_amount_to_sell = str(max_amount_to_sell)[0:len(min_lot_size.split('.')[1]) +
                                                   len(str(max_amount_to_sell).split('.')[0]) + 1]
        return final_amount_to_sell
    else:
        print('amount less than minimum order!')


def execute_sell(what_to_sell, what_for, share):
    ## ПОСТАВИМ ОРДЕР НА ПРОДАЖУ
    try:
        order_sell = client.create_order(symbol=what_to_sell + what_for,
                                         side=Client.SIDE_SELL,
                                         type=Client.ORDER_TYPE_MARKET,
                                         newOrderRespType='FULL',
                                         quantity=sell_func(what_to_sell, what_for, share))
        print('sell order', '\n', order_sell['symbol'], order_sell['fills'], flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'sell order executed :)) ' +\
                                       str(order_sell['symbol']) + ' '+\
                                       str(order_sell['fills']) + ' '+\
                                       str(float(order_sell['fills'][0]['price'])*float(order_sell['fills'][0]['qty'])))
    except:
        print('error ... probably not enough money', flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'ERROR executing sell order!!')
    finally:
        print( tg_tmp['result']['chat'], '\n', tg_tmp['ok'],' Telegram message sent!')

def telegram_bot_sendtext(bot_token, bot_chatID ,bot_message):
    send_text = 'https://api.telegram.org/bot'+ bot_token + '/sendMessage?chat_id='+ bot_chatID + '&text='+ bot_message
    print(send_text)
    return requests.get(send_text).json()




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
        print(mail['Subject'], mail['Date'], flush=True)
        telegram_bot_sendtext(telegram_bot_token,
                                   telegram_bot_chatID,
                                   'Mail Recieved: '+mail['Subject'] + ' ' + mail['Date'])
        if 'Buy' in mail['Subject']:
            execute_buy(mail['Subject'].split('_')[2],
                        'USDT',
                        1)
        elif 'TP1' in mail['Subject']:
            execute_sell(mail['Subject'].split('_')[2],
                        'USDT',
                        0.33)
        elif 'TP2' in mail['Subject']:
            execute_sell(mail['Subject'].split('_')[2],
                        'USDT',
                        0.5)
        elif 'TP3' in mail['Subject']:
            execute_sell(mail['Subject'].split('_')[2],
                        'USDT',
                        1)
        elif 'Sell' in mail['Subject']:
            execute_sell(mail['Subject'].split('_')[2],
                        'USDT',
                        1)
        else:
            print('Unknown email', flush=True)
        print('Deleting email', flush=True)
        connector.store(emailid, '+FLAGS', '\\Deleted')
        connector.expunge()
    print('done ', dt.datetime.now(), flush=True)

    connector.close()
    connector.logout()


#connector.close()
#connector.logout()
