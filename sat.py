api_key = 'test'
api_secret = 'test'
mail_pass = 'test'
mail_host = 'imap.gmail.com'
mail_login = 'test'
telegram_bot_token = 'test'
telegram_bot_chatID = 'test'
to_trade = ['BTC','ETH','XRP','EOS','BSV','ADA']
take_profits = {
                 'TP1':[0.045, 0.12],
                 'TP2':[0.095, 0.22],
                 'TP3':[0.135, 0.32],
                 'TP4':[0.175, 0.22],
                 'TP5':[0.225, 0.12]
               }



import requests
import imaplib
import email
import numpy as np
import pandas as pd
import time
import datetime as dt
from binance.client import Client
client = Client(api_key, api_secret)


def smart_split(to_trade, mode = 'und'):
    balances_full = pd.DataFrame(client.get_account()['balances']).rename(columns={'asset':'symbol'})
    balances_full['free'] = balances_full['free'].astype(float)
    prices = pd.DataFrame(client.get_symbol_ticker())
    prices['symbol'] = prices['symbol'].str.replace('USDT','')
    balances_actual = balances_full[balances_full['free']>0]
    balances_actual = pd.merge(balances_actual, prices , on='symbol', how='left').fillna(1)
    balances_actual['price'] = balances_actual['price'].astype(float)
    balances_actual['usd'] = balances_actual['price']*balances_actual['free']
    balance_benchmark = sum(balances_actual['usd'])/len(to_trade)*0.05
    balances_actual['in_action'] = balances_actual['usd']>balance_benchmark
    cur_in_action = balances_actual[(balances_actual['in_action']) & (balances_actual['symbol']!='USDT')]
    cur_left = (len(to_trade)-2 - len(cur_in_action))
    if cur_left>0:
        use_next_deal = balances_actual[(balances_actual['symbol']=='USDT')]['free'].sum()/cur_left
    else:
        use_next_deal=0
    if mode =='und':
        return use_next_deal
    else:
        return cur_in_action


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
        qty_purched = pd.DataFrame(order_buy['fills'])['qty'].astype(float).sum()
        price_purched = pd.DataFrame(order_buy['fills'])['price'].astype(float).mean()

        print('buy order', '\n', order_buy['symbol'], order_buy['fills'], str(qty_purched*price_purched), flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'buy order executed :)) ' +\
                                       str(order_buy['symbol']) + ' '+\
                                       str(order_buy['fills']) + ' '+\
                                       str(qty_purched*price_purched))
        return {'price':price_purched,'qty': qty_purched}
    except:
        print('error ... probably not enough money', flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'ERROR executing buy order!!')
    finally:
        print( tg_tmp['result']['chat'], '\n', tg_tmp['ok'],' Telegram message sent!')


def sell_func(what_to_sell, what_for, share, val=None):
    ticker = what_to_sell + what_for
    balance_atm = client.get_asset_balance(asset=what_to_sell)
    price_atm = client.get_symbol_ticker(symbol=ticker)
    ticker_info = client.get_symbol_info(ticker)
    min_notional = {i['filterType']:i['minNotional'] for i in ticker_info['filters'] if i['filterType']=='MIN_NOTIONAL'}

    max_amount_to_sell = np.format_float_positional(float(balance_atm['free'])*share) if val==None else val
    min_amount_to_sell = np.format_float_positional(float(min_notional['MIN_NOTIONAL'])/float(price_atm['price']))

    if float(max_amount_to_sell)>float(min_amount_to_sell):
        min_lot_size = {i['filterType']:i['minQty'] for i in ticker_info['filters'] if i['filterType']=='LOT_SIZE'}
        min_lot_size = np.format_float_positional(float(min_lot_size['LOT_SIZE']))
        final_amount_to_sell = str(max_amount_to_sell)[0:len(min_lot_size.split('.')[1]) +
                                                   len(str(max_amount_to_sell).split('.')[0]) + 1]
        return final_amount_to_sell
    else:
        print('amount less than minimum order!')


def execute_sell(what_to_sell, what_for, share, val=None):
    ## ПОСТАВИМ ОРДЕР НА ПРОДАЖУ
    try:
        order_sell = client.create_order(symbol=what_to_sell + what_for,
                                         side=Client.SIDE_SELL,
                                         type=Client.ORDER_TYPE_MARKET,
                                         newOrderRespType='FULL',
                                         quantity=sell_func(what_to_sell, what_for, share, val))
        qty_sold = pd.DataFrame(order_sell['fills'])['qty'].astype(float).sum()
        price_sold = pd.DataFrame(order_sell['fills'])['price'].astype(float).mean()

        print('sell order', '\n', order_sell['symbol'], order_sell['fills'], str(qty_sold*price_sold), flush=True)
        tg_tmp = telegram_bot_sendtext(telegram_bot_token,
                                       telegram_bot_chatID,
                                       'sell order executed :)) ' +\
                                       str(order_sell['symbol']) + ' '+\
                                       str(order_sell['fills']) + ' '+\
                                       str(qty_sold*price_sold))
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


## Объект трекающий тейкпрофиты
class TakeProfitsTracker():
    def __init__(self, take_profits):

        self.tp_dict = take_profits
        self.price_changes = {i:take_profits[i][0] for i in take_profits}
        self.share_to_trade = {i:take_profits[i][1] for i in take_profits}

        cur_in_action = smart_split(to_trade, mode = 'cia')

        self.amount_buy = {}
        self.prices_buy = {}
        self.prices_marks = {}

        for i in cur_in_action['symbol']:
            newi = i +'USDT'
            tmp = pd.DataFrame(client.get_my_trades(symbol = newi, limit=20)
                            ).sort_values(by='time',ascending=False
                                     ).query('isBuyer==True'
                                            ).drop_duplicates(subset='symbol')['price']
            self.amount_buy[newi] = cur_in_action[cur_in_action['symbol']==i]['free'].sum()
            self.prices_buy[newi] = float(tmp)
            self.prices_marks[newi] = {j:float(tmp) * (self.price_changes[j]+1) for j in self.price_changes}

    def cur_purchased_from_signal(self, ticker, price_buy, amount):
        self.amount_buy[ticker] = amount
        self.prices_buy[ticker] = price_buy
        self.prices_marks[ticker] = {i:float(price_buy) * (self.price_changes[i]+1) for i in self.price_changes}

    def cur_sold_from_signal(self, ticker):
        del self.amount_buy[ticker]
        del self.prices_buy[ticker]
        del self.prices_marks[ticker]

    def check_prices(self):
        for i in list(self.prices_marks.keys()):
            ## Если в списке тейкпрофитов больше не осталось значений, удаляем валюту из трекера
            if len(self.prices_marks[i])==0:
                self.cur_sold_from_signal(i)
                continue

            price_atm = client.get_symbol_ticker(symbol=i)['price']
            tp_signaled = [j for j in self.prices_marks[i] if self.prices_marks[i][j]<=float(price_atm)]
            if len(tp_signaled)>0:
                self.prices_marks[i] = {j:self.prices_marks[i][j] for j in self.prices_marks[i] if j not in tp_signaled}
                signal_share_sell = round(sum([self.share_to_trade[j] for j in tp_signaled]),3)
                signal_actual_sell = signal_share_sell*self.amount_buy[i]
                print('TAKE_PRIFIT_SIGNAL', price_atm, i, tp_signaled, signal_share_sell, 'TO_TRADE: ',signal_actual_sell)
                return {'ticker':i, 'val':signal_actual_sell}
                break
        print ( 'prices:',self.prices_buy, '\namount:',self.amount_buy, '\nTP_marks:', self.prices_marks)



take_profit_tracker = TakeProfitsTracker(take_profits)
#connector = imaplib.IMAP4_SSL(mail_host)
#connector.login(mail_login, mail_pass)



## ОСНОВНОЙ ЦИКЛ
while True:
    time.sleep(30)
    ## ПРОВЕРЯЕМ ТЕЙКПРОФИТЫ
    res = take_profit_tracker.check_prices()
    if res!=None:
        execute_sell(what_to_sell=res['ticker'].replace('USDT',''), what_for='USDT', share=1, val =res['val'])




    ## ПРОВЕРЯМ ПОЧТУ
    connector = imaplib.IMAP4_SSL(mail_host)
    connector.login(mail_login, mail_pass)
    connector.select("TradingView_Alerts")
    resp, items = connector.search(None, "ALL")

    for emailid in items[0].split():
        currency = None
        tmp = None
        resp, data = connector.fetch(emailid, '(RFC822)')
        mail = email.message_from_bytes(data[0][1])
        print(mail['Subject'], mail['Date'], flush=True)
        telegram_bot_sendtext(telegram_bot_token,
                                   telegram_bot_chatID,
                                   'Mail Recieved: '+mail['Subject'] + ' ' + mail['Date'])
        if 'Buy' in mail['Subject']:
            currency = mail['Subject'].split('_')[2]
            tmp = execute_buy(what_to_buy=currency, what_for='USDT', share=1)
            try:
                take_profit_tracker.cur_purchased_from_signal(currency+'USDT', tmp['price'], tmp['qty'])
            except:
                print('Tracker_ERROR: price_and_amount_not_passed')

        elif 'Sell' in mail['Subject']:
            currency = mail['Subject'].split('_')[2]
            execute_sell(what_to_sell=currency, what_for='USDT', share=1)
            try:
                take_profit_tracker.cur_sold_from_signal(currency+'USDT')
            except:
                print('Tracker_ERROR: currency_doesnt_exist')

        else:
            print('Unknown email', flush=True)
        print('Deleting email', flush=True)
        connector.store(emailid, '+X-GM-LABELS', '\\Trash')
    connector.expunge()
    print('done ', dt.datetime.now(), flush=True)

    connector.close()
    connector.logout()


#connector.close()
#connector.logout()
