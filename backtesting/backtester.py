#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import itertools

import numpy as np
import pandas as pd

from sklearn.model_selection import PredefinedSplit, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, precision_score, recall_score

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import style

from policy import AllInOutPolicy
from portfolio import BacktestPortfolio
from utils import progress_bar

style.use('ggplot')

class Backtester:
    def __init__(self, X, y, returns, asset_name, models, policy):
        self.X = X
        self.y = y
        self.returns = returns
        self.asset_name = asset_name

        self.models = models
        self.policy = policy

        self.backtest_periods = []
        self.model_names = list(self.models.keys())
        self.portfolios = {name: BacktestPortfolio() for name in self.model_names}
    
    def _benchmark_metrics(self):
        start = self.backtest_periods[0]['Test'][0]
        end = self.backtest_periods[-1]['Test'][1]

        y_true = self.y[start:end]
        returns = self.returns[start:end]

        self.bnh_policy = AllInOutPolicy()
        self.bnh_portfolio = BacktestPortfolio()

        predictions = np.ones(len(self.y[start:end]), dtype = int)
        signals = self.bnh_policy.generate_signals(predictions)

        self.bnh_portfolio.calc_error_metrics(predictions, y_true)
        self.bnh_portfolio.calc_profitability_metrics(signals, returns)
    
    def generate_periods(self, split, single_split = True, window = -1):
        train_start = split['Train'][0]
        train_end = split['Train'][1]
        test_start = split['Test'][0]
        test_end = split['Test'][1]
        
        if single_split:
            self.backtest_periods.append({'Train': (train_start, train_end), 'Test': (test_start, test_end)})
        
        else:
            i = train_start
            training_days = train_end - train_start
            
            while i + training_days + window <= test_end:
                self.backtest_periods.append({'Train': (i, i + training_days), 'Test': (i + training_days, i + training_days + window)})
                
                i += window

        self.backtest_periods[-1]['Test'] = (self.backtest_periods[-1]['Test'][0], len(self.X))
    
    def _predict(self):
        X = self.X
        y = self.y

        self.predictions = {name: [] for name in self.model_names}

        n = len(self.backtest_periods)

        progress_bar(0, n, prefix = 'Backtesting:', length = 50)

        for name in self.model_names:
            model = self.models[name]
            i = 0

            for P in self.backtest_periods:
                train_i = P['Train']
                test_i = P['Test']

                X_train = X[train_i[0]:train_i[1]]
                y_train = y[train_i[0]:train_i[1]]

                X_test = X[test_i[0]:test_i[1]]
                y_test = y[test_i[0]:test_i[1]]

                X_train = StandardScaler().fit_transform(X_train)
                X_test = StandardScaler().fit_transform(X_test)

                model.fit(X_train, y_train, batch_size = 50, epochs = 100, verbose = 0)

                predictions = model.predict(X_test)[:, 0]
                P = [1 if p >= 0.5 else 0 for p in predictions]

                self.predictions[name].append(P)

                progress_bar(i, n, prefix = 'Backtesting:', length = 50)
                i += 1
            
            #progress_bar(n, n, prefix = 'Backtesting:', length = 50)
            
            self.predictions[name] = list(itertools.chain.from_iterable(self.predictions[name]))
    
    def plot_CR(self):
        #plt.plot(self.portfolio.cumulative_return, label = self.model.name)
        for name in self.model_names:
            plt.plot(self.portfolios[name].cumulative_return, label = name)

        plt.plot(self.bnh_portfolio.cumulative_return, label = 'Buy & Hold')

        plt.ylabel('Cumulative Return')
        plt.xlabel('Time')
        plt.title('Cumulative Return for {}'.format(self.asset_name))
        plt.legend(loc = 2)

        plt.show()
    
    def test(self):
        start = self.backtest_periods[0]['Test'][0]
        end = self.backtest_periods[-1]['Test'][1]

        y_true = self.y[start:end]
        returns = self.returns[start:end]

        self._predict()

        for name in self.model_names:
            signals = self.policy.generate_signals(self.predictions[name])

            self.portfolios[name].calc_error_metrics(self.predictions[name], y_true)
            self.portfolios[name].calc_profitability_metrics(signals, returns)
        
        self._benchmark_metrics()
    
    def report(self):
        start = self.backtest_periods[0]['Test'][0]
        end = self.backtest_periods[-1]['Test'][1]

        bnh_error_metrics = pd.DataFrame([self.bnh_portfolio.error_metrics], columns = ['Accuracy', 'Precision', 'Recall', 'F1 Score'], index = ['Buy & Hold'])
        bnh_profitability_metrics = pd.DataFrame([self.bnh_portfolio.profitability_metrics], columns = ['CR', 'AR', 'AV', 'SR'], index = ['Buy & Hold'])

        error_metrics_report = pd.DataFrame([self.portfolios[name].error_metrics for name in self.model_names], columns = ['Accuracy', 'Precision', 'Recall', 'F1 Score'], index = self.model_names)
        profitability_metrics_report = pd.DataFrame([self.portfolios[name].profitability_metrics for name in self.model_names], columns = ['CR', 'AR', 'AV', 'SR'], index = self.model_names)

        print()
        print('Performance metrics for:', self.asset_name)
        print('Testing period: {} to {}'.format(self.X.index[start], self.X.index[end - 1]))
        print()

        print('------------------BnH Error Metrics----------------')
        print(bnh_error_metrics)
        print()

        print('------------BnH Profitability Metrics------------')
        print(bnh_profitability_metrics)
        print()

        print('-----------------Error Metrics----------------')
        print(error_metrics_report)
        print()

        print('-------------Profitability Metrics-----------')
        print(profitability_metrics_report)
        print()

        self.plot_CR()