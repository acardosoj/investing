from time import sleep
import pandas as pd 
import yaml
import sys
import numpy as np
from .fundamentus import fundamentus, advfn
from .b3 import b3
from .fundos import fundos
from .DSManager import Manager
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from tqdm import tqdm
import json

class DailyExtractor:
    def __init__(self, project_dir, assets = None, interval = "1m"):
        self.path = Path(__file__).parent
        self.manager = Manager(project_dir)
        self.dir = Path(project_dir)
        self.assets = assets
        self.assets.extend([x + "_history" for x in assets])
        self.interval = interval
        self.b3_api = b3.B3()

    def run(self, baseline_date = None):
        print("Extracting Intraday data \n")
        dates = {}
        if baseline_date is None:
            dates = self.manager.get_latest_dates()
        else:
            for asset in self.assets:
                dates[asset] = baseline_date

        for asset in self.assets: 
            print("Starting for asset", asset, "\n")
            initial = dates[asset]
            asset_name = asset.split("_history")[0]
            if "history" in asset:
                data = self.get_data(initial, asset_name, history = True)
            else:
                data = self.get_data(initial, asset_name)
            if len(data) > 0:
                self.manager.append_data(data, asset)

    def __get_tickers(self, asset):
        with open(self.dir / asset / "config.json", 'r') as f:
            config = json.load(f)
        return config['TICKERS']

    def get_data(self, date, asset, history = False):
        inter = self.interval
        if history:
            inter = '1d'
        data = pd.DataFrame([])
        if asset == "b3":
            data = self.__extract_intraday(asset, self.__get_tickers(asset), date, inter)
        elif asset == "cripto":
            data = self.__extract_intraday(asset, self.__get_tickers(asset), date, inter)
        elif asset == "b3_funds":
            data = self.__extract_intraday(asset, self.__get_tickers(asset), date, inter)
        elif asset == "funds":
            if history:
                data = self.__extract_funds_history(date) 
        else:
            raise Exception(f"Asset {asset} not supported")

        return data

    def random_wait(self):
        wait_times = [0.2, 0.5, 1, 2, 4]
        probs = [0.3, 0.4, 0.2, 0.08, 0.02]
        choice = np.random.choice(wait_times, size=1, p=probs)
        sleep(choice[0])

    def __extract_funds_history(self, date):
        result = fundos.get_data(date.strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d"), min_cot = 100)
        result = result.rename(columns = {'DT_COMPTC' : 'DATE', 'CNPJ_FUNDO': "TICKER"})
        result = result[pd.to_datetime(result['DATE']) >= date]
        return result

    def __extract_intraday(self, asset, tickers, date, interval):
        now = datetime.now()
        delta = (now - date).days
        if  delta > 30 and interval != "1d" and interval != "1h":
            date = now + relativedelta(days = -30)
        
        date_intervals = [(date, now)]

        if delta > 7 and interval == "1m":
            date_intervals = []
            current = date 
            while current < now:
                final = current + relativedelta(days = 7)
                if final > now:
                    final = now
                date_intervals.append((current, final))
                current = current + relativedelta(days = 8)
        
        all_data = pd.DataFrame([])
        errors = []
        for ticker in tqdm(tickers):
            for dt_interval in date_intervals:
                try:
                    data = self.b3_api.Extract_Data(ticker, start = dt_interval[0].strftime("%Y-%m-%d"), end = dt_interval[1].strftime("%Y-%m-%d"), interval = interval)
                    data = data.reset_index().rename(columns = {"symbol" : "TICKER", "date" : "DATE"})
                    all_data = all_data.append(data)
                except Exception as e: 
                    print("Could not load data from", ticker, "\n")
                    print(e)
                    errors.append(ticker)
                self.random_wait()

        log_file = datetime.now().strftime("%Y%m%d") +"_log.txt"
        with open(self.dir / asset / log_file, 'w') as f:
            f.write('\n'.join(errors))

        return all_data
        