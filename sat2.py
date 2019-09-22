api_key = 'test'
api_secret = 'test'
telegram_bot_token = 'test'
telegram_bot_chatID = 'test'
telegram_api_id = test
telegram_api_hash = 'test'
telegram_phone_number = test
to_trade = test




from telethon import TelegramClient, events
import requests
import re
import pandas as pd
import numpy as np
import time
from binance.client import Client
client = Client(api_key, api_secret)


def smart_split(what_to_buy, mode = 'und'):
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
    if what_to_buy in cur_in_action['symbol'].unique() or cur_left>0:
        use_next_deal = (balances_actual['usd'].sum()-5)/(len(to_trade)-2)
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
    max_amount_to_buy = np.format_float_positional((smart_split(what_to_buy)/float(price_atm['price']))*share)
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


def get_last_messages(avail_time = 120):
    while True:
        time.sleep(15)
        tmp = requests.get('https://api.telegram.org/bot'+ telegram_bot_token + '/getUpdates?limit=1&offset=-1').json()
        try:
            code_time = tmp['result'][0]['message']['date']
        except:
            print('no message')
            continue
        diff_time = time.time() - code_time
        if diff_time<avail_time:
            print('code is fresh!')
            code = re.findall('\d+', tmp['result'][0]['message']['text'])
            print(code[0])
            return code[0]
        else:
            print('code_is_old')
            requests.get('https://api.telegram.org/bot'+ telegram_bot_token + '/sendMessage?chat_id='+ telegram_bot_chatID +'&text=waiting_for_code').json()


async def auth_tg():
    await telegram_client.send_code_request(telegram_phone_number, force_sms=False)
    res = get_last_messages()
    return res

## telegram auth
## dont forget to turn off 2fa!
telegram_client = TelegramClient(session=None,
                        api_id=telegram_api_id,
                        auto_reconnect=True,
                        api_hash=telegram_api_hash)
telegram_client.start(phone=telegram_phone_number, code_callback = auth_tg)
## send code to bot like this  '12345_' !



cur_search = re.compile('[a-zA-Z]+(?=\/)')
action_search = re.compile('(?<=Позиция: ).+?(?=\\n|$)')
symbols = re.compile('[,.\\\/\%\$0-9]')
numbers = re.compile('\d+(?=\%)')


Position_dict = {'продать не шортить':'Long_Close',
 'продать половину':'Long_Close',
 'закрыть покупку':'Long_Close',
 'закрыть покупкуlong':'Long_Close',
 'открыть продажуshort на ':'Short_Open',
 'закрыть продажуshort':'Short_Close',
 'откупить шорт':'Short_Close',
 'продажаshort':'Short_Open',
 'покупка (закрыть short взять long на )':'Long_Open',
 'покупкаlong':'Long_Open',
 'покупкаlong на ':'Long_Open',
 'покупкаlong на ':'Long_Open'}

## Main loop
@telegram_client.on(events.NewMessage)
async def normal_handler(event):
    print(event.message)
    print(event.message.to_dict()['message'])
    new_message = event.message.to_dict()['message']
    if 'hello' in new_message:
        await event.reply('Kek')
    if 'USD' in new_message:
        res =  pd.DataFrame({'cur':[],
                             'value':[],
                             'test':[],
                             'action':[]})
        for signal_id in new_message.split('\n\n'):
            res = res.append({'cur':re.search(cur_search, signal_id).group(),
                              'value':''.join(re.findall(numbers, signal_id)) or '100',
                              'test':re.search(action_search, signal_id).group(),
                              'action':re.sub(symbols,'',re.search(action_search, signal_id).group()
                                    ).replace('  ',' ').lower()},ignore_index=True)
            res['true_action'] = res['action'].replace(Position_dict)
            res.loc[res['test'].str.contains('полов'),'value']='50'
            res.loc[res['test'].str.contains('четверть'),'value']='25'
        print(res)
        for i in range(len(res)):
            if res.loc[i]['true_action'] == 'Long_Open':
                print('WILL BUY', res.loc[i]['cur'])
                print(buy_func(res.loc[i]['cur'],
                               'USDT',
                               int(res.loc[i]['value'])/100))
            elif res.loc[i]['true_action'] == 'Long_Close':
                print('WILL SELL', res.loc[i]['cur'])
                print(sell_func(res.loc[i]['cur'],
                               'USDT',
                               int(res.loc[i]['value'])/100))


telegram_client.run_until_disconnected()



##  Напечатать существующие диалоги
#for dialog in telegram_client.iter_dialogs():
#    print(dialog.name, 'has ID', dialog.id)



async def main_logout():
    await telegram_client.connect()
    await telegram_client.log_out()
    await telegram_client.disconnect()


telegram_client.loop.run_until_complete(main_logout())

