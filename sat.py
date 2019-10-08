api_key = 'test'
api_secret = 'test'
mail_pass = 'test'
mail_host = 'imap.gmail.com'
mail_login = 'test'
telegram_bot_token = 'test'
telegram_bot_chatID = 'test'
to_trade = ['BTC','ETH','XRP','EOS','LTC','ADA']
TO_TRADE = 6
take_profits = {
                 'TP1':[0.045, 0.20],
                 'TP2':[0.095, 0.20],
                 'TP3':[0.135, 0.20],
                 'TP4':[0.175, 0.20],
                 'TP5':[0.225, 0.20]
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




def smart_split(cur='BTC' ,mode = 'use_next_deal'):
    balances_full = pd.DataFrame(client.get_margin_account()['userAssets']).rename(columns={'asset':'symbol'})
    balances_full['netAsset'] = balances_full['netAsset'].astype(float)
    prices = pd.DataFrame(client.get_symbol_ticker())
    prices['symbol'] = prices['symbol'].str.replace('USDT','')
    balances_actual = balances_full[balances_full['netAsset']!=0]
    balances_actual = pd.merge(balances_actual, prices , on='symbol', how='left').fillna(1)
    balances_actual['price'] = balances_actual['price'].astype(float)
    balances_actual['usd'] = balances_actual['price']*balances_actual['netAsset']
    balances_actual['usd_true'] = np.where(balances_actual['usd']<0, balances_actual['usd']*2, balances_actual['usd'])
    balances_actual['position'] = np.where(balances_actual['usd']<0, 'short', 'long')
    balance_benchmark = sum(balances_actual['usd'])/TO_TRADE*0.05
    balances_actual['in_action'] = abs(balances_actual['usd'])>balance_benchmark
    cur_in_action = balances_actual[(balances_actual['in_action']) & (balances_actual['symbol']!='USDT')]

    cur_left = (TO_TRADE - len(cur_in_action))
    use_next_deal = balances_actual[(balances_actual['usd_true']<0) | (balances_actual['symbol']=='USDT')]['usd_true'].sum()-100
    use_next_deal = use_next_deal/cur_left if (cur_left and cur not in list(cur_in_action['symbol'])) else 0

    if mode =='use_next_deal':
        return use_next_deal
    elif mode == 'cur_in_action':
        return cur_in_action


def get_order_amount(deal_type , cur, share, val):
    ticker = cur + 'USDT'
    ticker_info = client.get_symbol_info(symbol=ticker)
    price_atm = client.get_symbol_ticker(symbol=ticker)
    min_notional = {i['filterType']: i['minNotional'] for i in ticker_info['filters'] if i['filterType'] == 'MIN_NOTIONAL'}
    min_lot_size = float({i['filterType']: i['minQty'] for i in ticker_info['filters'] if i['filterType'] == 'LOT_SIZE'}['LOT_SIZE'])
    min_amount = float(min_notional['MIN_NOTIONAL'])/float(price_atm['price'])

    if deal_type == 'close':
        margin_assets = pd.DataFrame(client.get_margin_account()['userAssets'])
        margin_assets.iloc[:,1:] = margin_assets.iloc[:,1:].astype(float)
        margin_assets['netAsset_noInterest'] = -margin_assets['borrowed']+margin_assets['free']

        balance_atm = margin_assets.loc[margin_assets['asset']==cur]['netAsset_noInterest'].values[0]*share
        interest = margin_assets.loc[margin_assets['asset']==cur]['interest'].values[0]
        balance_atm = balance_atm - interest

        balance_atm = balance_atm - np.sign(balance_atm)*balance_atm*0.001 - float(min_lot_size) ## added comission for shorts
        max_amount = val or abs(balance_atm)
    elif deal_type == 'open':
        max_amount = val or (smart_split(cur=cur, mode = 'use_next_deal')/float(price_atm['price']))*share


    if max_amount > min_amount:
        min_lot_size = np.format_float_positional(min_lot_size)
        max_amount = np.format_float_positional(max_amount)
        final_amount = max_amount[0:len(min_lot_size.split('.')[1]) + len(str(max_amount).split('.')[0]) + 1]
        return final_amount
    else:
        print('amount less than minimum order!', flush=True)


def execute_order(deal_type, position , cur, share, val):
    q = get_order_amount(deal_type, cur, share, val)
    if position =='long' and deal_type =='open':
        s = Client.SIDE_BUY
    elif position =='long' and deal_type == 'close':
        s = Client.SIDE_SELL
    elif position =='short' and deal_type == 'open':
        s = Client.SIDE_SELL
    elif position =='short' and deal_type == 'close':
        s = Client.SIDE_BUY

    ## ПОСТАВИМ ОРДЕР
    order = client.create_margin_order(symbol=cur + 'USDT',
                                    side=s,
                                    type=Client.ORDER_TYPE_MARKET,
                                    newOrderRespType='FULL',
                                    quantity=q)
    qty = pd.DataFrame(order['fills'])['qty'].astype(float).sum()
    price = pd.DataFrame(order['fills'])['price'].astype(float).mean()
    print(position, deal_type, 'order executed!', '\n', order['symbol'], order['fills'], str(qty*price), flush=True)
    telegram_bot_sendtext(telegram_bot_token,
                                   telegram_bot_chatID,
                                   position + ' '+ deal_type + ' ' + 'order executed!' + ' ' +\
                                   str(order['symbol']) + ' '+\
                                   str(order['fills']) + ' '+\
                                   str(qty*price))
    return {'price':price,'qty': qty}


def telegram_bot_sendtext(bot_token, bot_chatID ,bot_message):
    send_text = 'https://api.telegram.org/bot'+ bot_token + '/sendMessage?chat_id='+ bot_chatID + '&text='+ bot_message
    print(send_text)
    return requests.get(send_text).json()


def loan_dealer(action_type, cur, share, val):
    if action_type == 'create':
        amount = get_order_amount(deal_type='open', cur=cur, share=share, val=val)
        client.create_margin_loan(asset=cur, amount=amount)

        return execute_order(deal_type='open', position='short', cur=cur, share=share ,val=float(amount))

    elif action_type == 'repay':
        execute_order(deal_type='close', position='short', cur=cur, share=share, val=val )

        repay_df = pd.DataFrame(client.get_margin_account()['userAssets'])
        rp_val = str(repay_df.loc[repay_df['asset']==cur]['free'].values[0])
        client.repay_margin_loan(asset=cur, amount=rp_val)



## Объект трекающий тейкпрофиты
class TakeProfitsTracker():
    def __init__(self, take_profits):

        self.tp_dict = take_profits
        self.price_changes = {i:take_profits[i][0] for i in take_profits}
        self.share_to_trade = {i:take_profits[i][1] for i in take_profits}

        cur_in_action = smart_split(mode='cur_in_action')

        self.amount_open = {}
        self.prices_open = {}
        self.prices_marks = {}
        self.position_types = {}

        for i in cur_in_action['symbol']:
            ## GET LATEST SYMBOL DATA
            newi = i +'USDT'
            self.position_types[newi] = cur_in_action[cur_in_action['symbol']==i]['position'].values[0]
            latest_symbol_data = pd.DataFrame(client.get_margin_trades(symbol = newi, limit=50)
                                             ).query('isBuyer=={IsLong}'.format(IsLong = self.position_types[newi]=='long'))
            latest_symbol_data['quoteQty'] = latest_symbol_data['price'].astype(float)*latest_symbol_data['qty'].astype(float)
            latest_symbol_data[['qty','quoteQty','time']] = latest_symbol_data[['qty','quoteQty','time']].apply(pd.to_numeric, errors='coerce')
            latest_symbol_data = latest_symbol_data.groupby(['time','orderId','symbol']
                                                           ).agg({'quoteQty':'sum', 'qty':'sum'}
                                                                ).reset_index()
            latest_symbol_data['price'] = latest_symbol_data['quoteQty']/latest_symbol_data['qty']
            latest_symbol_data = latest_symbol_data.sort_values(by='time',ascending=False
                                                               ).drop_duplicates(subset='symbol')

            self.amount_open[newi] = float(latest_symbol_data['qty'])
            self.prices_open[newi] = float(latest_symbol_data['price'])

            ## GET THE LIST OF PROFITS TAKEN
            share_left = abs(cur_in_action[cur_in_action['symbol']==i]['netAsset'].sum())/self.amount_open[newi]
            changing_share_sum = 1
            profits_taken = []
            for j,i in take_profits.items():
                changing_share_sum-=i[1]

                if changing_share_sum<share_left:
                    break
                profits_taken+=[j]

            self.get_prices_marks(ticker=newi, price_buy=float(latest_symbol_data['price']), profits_taken=profits_taken)

    def get_prices_marks(self, ticker, price_buy, profits_taken):
            if self.position_types[ticker] =='long':
                self.prices_marks[ticker] = {i:price_buy * (self.price_changes[i]+1) for i in self.price_changes if i not in profits_taken}
            elif self.position_types[ticker] =='short':
                self.prices_marks[ticker] = {i:price_buy * (1-self.price_changes[i]) for i in self.price_changes if i not in profits_taken}

    def position_opened_from_signal(self, position, ticker, price_buy, amount):
        self.amount_open[ticker] = amount
        self.prices_open[ticker] = price_buy
        self.position_types[ticker] = position
        self.get_prices_marks(ticker=ticker, price_buy=float(price_buy), profits_taken=[])

    def position_closed_from_signal(self, ticker):
        del self.amount_open[ticker]
        del self.prices_open[ticker]
        del self.position_types[ticker]
        del self.prices_marks[ticker]

    def check_prices(self, test=None):
        for i in list(self.prices_marks.keys()):
            ## Если в списке тейкпрофитов больше не осталось значений, удаляем валюту из трекера
            if len(self.prices_marks[i])==0:
                self.position_closed_from_signal(i)
                continue

            ## Проверим сработали ли тейкпрофиты
            price_atm = test or client.get_symbol_ticker(symbol=i)['price']
            if self.position_types[i] =='long':
                tp_signaled = [j for j in self.prices_marks[i] if self.prices_marks[i][j]<=float(price_atm)]
            elif self.position_types[i] =='short':
                tp_signaled = [j for j in self.prices_marks[i] if self.prices_marks[i][j]>=float(price_atm)]

            ## Вернем сумму сделки
            if len(tp_signaled)>0:
                self.prices_marks[i] = {j:self.prices_marks[i][j] for j in self.prices_marks[i] if j not in tp_signaled}
                signal_share_close = round(sum([self.share_to_trade[j] for j in tp_signaled]),3)
                signal_val_close = signal_share_close*self.amount_open[i]

                margin_assets = pd.DataFrame(client.get_margin_account()['userAssets'])
                margin_assets['asset'] = margin_assets['asset']+'USDT'

                if self.position_types[i] =='long':
                    signal_actual_close = signal_val_close/float(margin_assets[margin_assets['asset']==i]['free'].values[0])
                elif self.position_types[i] =='short':
                    signal_actual_close = signal_val_close/float(margin_assets[margin_assets['asset']==i]['borrowed'].values[0])

                print('TAKE_PRIFIT_SIGNAL', price_atm, i, tp_signaled, signal_share_close, 'TO_TRADE: ',signal_actual_close)
                return {'ticker':i, 'val':signal_actual_close, 'position_type':self.position_types[i]}
                break

        print ('prices:',self.prices_open,
               '\namount:',self.amount_open,
               '\nTP_marks:', self.prices_marks,
               '\nposition_types', self.position_types)




take_profit_tracker = TakeProfitsTracker(take_profits)
connector = imaplib.IMAP4_SSL(mail_host)
connector.login(mail_login, mail_pass)

## ОСНОВНОЙ ЦИКЛ
while True:
    time.sleep(60)
    ## ПРОВЕРЯЕМ ТЕЙКПРОФИТЫ
    res = take_profit_tracker.check_prices()
    if res!=None:
        share_trade_tmp = round(res['val'],3) if res['val']<=1 else 1
        if res['position_type']=='long':
            execute_order(deal_type='close', position='long' , cur=res['ticker'].replace('USDT',''), share=share_trade_tmp, val=None)
        elif res['position_type']=='short':
            loan_dealer(action_type='repay', cur=res['ticker'].replace('USDT',''), share=share_trade_tmp, val=None)




    ## ПРОВЕРЯМ ПОЧТУ
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
            try:
                loan_dealer(action_type='repay', cur=currency, share=1, val=None)
                take_profit_tracker.position_closed_from_signal(currency+'USDT')
            except:
                text = 'ERROR closing short'
                print(text, flush=True)
                telegram_bot_sendtext(telegram_bot_token, telegram_bot_chatID, text)

            try:
                tmp = execute_order(deal_type='open', position='long' , cur=currency, share=1, val=None)
                take_profit_tracker.position_opened_from_signal(position='long', ticker=currency+'USDT', price_buy=tmp['price'], amount=tmp['qty'])
            except:
                text = 'ERROR: opening long'
                print(text, flush=True)
                telegram_bot_sendtext(telegram_bot_token, telegram_bot_chatID, text)
        elif 'Sell' in mail['Subject']:
            currency = mail['Subject'].split('_')[2]
            try:
                execute_order(deal_type='close', position='long' , cur=currency, share=1, val=None)
                take_profit_tracker.position_closed_from_signal(currency+'USDT') ## изменить!
            except:
                text = 'ERROR: closing long'
                print(text, flush=True)
                telegram_bot_sendtext(telegram_bot_token, telegram_bot_chatID, text)
            try:
                tmp = loan_dealer(action_type='create', cur=currency, share=1, val=None)
                take_profit_tracker.position_opened_from_signal(position='short', ticker=currency+'USDT', price_buy=tmp['price'], amount=tmp['qty'])
            except:
                text = 'ERROR: opening long'
                print(text, flush=True)
                telegram_bot_sendtext(telegram_bot_token, telegram_bot_chatID, text)
        else:
            print('Unknown email', flush=True)
        print('Deleting email', flush=True)
        connector.store(emailid, '+X-GM-LABELS', '\\Trash')
    connector.expunge()
    print('done ', dt.datetime.now(), flush=True)
    connector.close()



connector.logout()
