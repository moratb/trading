api_key = 'test'
api_secret = 'test'

from oauth2client.service_account import ServiceAccountCredentials
from binance.client import Client
import gspread
import datetime as dt

client = Client(api_key, api_secret)
balances_full = client.get_account()['balances']
balances_val = [i for i in balances_full if float(i['free'])>0]
balances_actual = {i['asset']:i['free'] for i in balances_val}
prices = {i['symbol'][:-4]:i['price'] for i in client.get_symbol_ticker() if i['symbol'] in [j+'USDT' for j in balances_actual.keys()]}
balances_actual_usd = {i:float(balances_actual[i])*float(prices[i]) if i in prices.keys() else float(balances_actual[i]) for i in balances_actual.keys()}

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
client = gspread.authorize(creds)
sheet = client.open('binance_balance').sheet1
full_data = sheet.get_all_records()
date = dt.date.today().strftime('%d.%m.%Y')
balance = sum(balances_actual_usd.values())
sheet.insert_row([date,balance], len(full_data)+2)

