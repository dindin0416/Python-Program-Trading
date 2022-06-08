
import datetime
import os

import numpy as np
import pandas as pd
from talib.abstract import *


# 計算開高低收
def CountOHLC(NameList, Prod):
    OHLC = open("OHLC.csv", "w")  # 記錄開高低收的檔案
    for name in NameList:
        # 日期
        Date = name[:8]
        data = []
        n = 60*24
        # print("Start:", Date)
        # 讀檔並整理資料
        rawData = open(path + name).readlines()
        data = [i.strip("\n").split(",") for i in rawData if i[13:17] == Prod]

        StartTime = datetime.datetime.strptime(Date + " 09000000", "%Y%m%d %H%M%S%f")
        Cycle = datetime.timedelta(0, 60 * n)
        # 定義空的 List 並將每分鐘資料存入
        KBar = []
        for i in data:
            # 時間、價格、成交量
            T = datetime.datetime.strptime(Date + " " + i[0], "%Y%m%d %H%M%S%f")
            P = i[2]
            V = int(i[3])
            # 同一根K棒
            if T < StartTime:
                # 最高價判斷
                KBar[-1][2] = max(P, KBar[-1][2])
                # 最低價判斷
                KBar[-1][3] = min(P, KBar[-1][3])
                # 收盤價更換
                KBar[-1][4] = P
                # 累計量
                KBar[-1][5] += V
            # 新增K棒
            else:
                while T >= StartTime:
                    # 起始時間 + 週期
                    StartTime += Cycle
                # 新增一根新的K棒 
                KBar.append([StartTime - Cycle, P, P, P, P, V])

        for i in KBar:
            i[0] = i[0].strftime("%Y%m%d %H%M%S%f")
            i[5] = str(i[5])
            # print(i)
            OHLC.write(",".join(i))
            OHLC.write("\n")

    OHLC.close()

# 把資料轉換成takbar格式的資料
def ReadOHLC():
    OHLC = open("OHLC.csv", "r")
    data = [i.strip("\n").split(",") for i in OHLC]
    TAKBar = {}
    # 分別取出時間、開、高、低、收、量，並轉換資料型態
    TAKBar["time"] = np.array([i[0] for i in data])
    TAKBar["open"] = np.array([float(i[1]) for i in data])
    TAKBar["high"] = np.array([float(i[2]) for i in data])
    TAKBar["low"] = np.array([float(i[3]) for i in data])
    TAKBar["close"] = np.array([float(i[4]) for i in data])
    TAKBar["volume"] = np.array([float(i[5]) for i in data])
    return TAKBar


path = "StockData/"  
Prod = "2330"  
NameList = os.listdir(path)  
print('資料處理中...')
CountOHLC(NameList, Prod)
Record = open("Record.csv", "w")

# 定義參數
BS = None
body_range=0.05 
head_length=0.5 
tail_length=2 
ma_period=9 
rsi_period=5 
rsi_oversell=30 
out_std=2 
QTY = 0
Capital = 5000000
OrderTime = 0
OrderPrice = 0
history_max = 0

# 計算策略需要的參數
stock = ReadOHLC()
stock=pd.DataFrame(stock)
stock['perday_change']=pd.DataFrame(stock['close']).pct_change()
stock["MA"] = SMA(stock, ma_period)
stock["20MA"] = SMA(stock, 20)
stock['RSI']=RSI(stock, rsi_period)
stock['STD']=pd.DataFrame(stock['close']).rolling(ma_period).std()
# 計算槌子線的細部參數
stock['st_body']=abs(stock['open']-stock['close'])
stock['s_head']=stock['high']-stock[['open','close']].max(axis=1)
stock['x_tail']=stock[['open','close']].min(axis=1) - stock['low']
stock['r_body']=np.where(stock['st_body']/stock['open']<body_range,True,False)
stock['r_head']=np.where(stock['s_head']==0,False,stock['s_head']/stock['x_tail']<head_length)
stock['r_tail']=np.where(stock['st_body']==0,True,stock['x_tail']/stock['st_body']>tail_length)
# k棒是否是槌子線 True/False
stock['hammer']=stock[['r_body','r_head','r_tail']].all(axis=1)

print('回測中...')
# 逐日讀取資料
for i in range(0,len(stock['time'])-1):
  # 更新每日的參數資料
  NextDate = stock.iloc[i+1]['time'][0:8]
  NextTime = stock.iloc[i+1]['time'][9:]
  NextOpen = stock.iloc[i+1]['open']
  LastRSI = stock.iloc[i-1]['RSI']
  Hammer = stock.iloc[i]['hammer']
  LastMA = stock.iloc[i-1]['MA']
  LastSTD = stock.iloc[i-1]['STD']
  LastLow = stock.iloc[i-1]['low']
  ThisClose = stock.iloc[i]['close']
  
  if i > 2 * ma_period:
    Condition1 = stock.loc[i - ma_period,'MA'] > LastMA     # 判斷趨勢是否向下
    Condition2 = LastRSI < rsi_oversell                     # 判斷rsi是否賣超
    Condition3 = Hammer                                     # 判斷k線是否為槌子線

    # 日期跑到最後一天如果還有部位則直接平倉
    if i == (len(stock['time'])-2) and QTY != 0:
        Record.write(
                ",".join(
                    [Prod, "S", str(NextDate), str(NextTime), str(NextOpen), str(QTY) + "\n"]
                )
            )
        BS = None
        QTY = 0

    # 如果日期不是最後一天則判斷要不要開倉進場
    elif not i == (len(stock['time'])-2):
      
      if BS == None:
        # 符合條件則進場
        if Condition1 and (Condition2 or Condition3):
          # 開倉日期
          OrderDate = NextDate
          # 開倉時間
          OrderTime = NextTime
          # 開倉價格
          OrderPrice = NextOpen
          # 開倉時的標準差
          long_gap=stock.loc[i-1,'STD']
          history_max = OrderPrice

          # 計算能夠買入的數量
          QTY = int(Capital // (OrderPrice * 1000))        
          # 計算剩餘資金
          Capital = Capital - QTY * 1000 * OrderPrice - OrderPrice * 0.001425   
          # 把交易紀錄寫進Record.csv
          Record.write(
              ",".join(
                  [Prod, "B", str(OrderDate), str(OrderTime), str(OrderPrice), str(QTY) + "\n"]
              )
          )
          BS = "B"
      
      elif BS == 'B':
          
        # 計算出場條件
        out = max(LastMA - out_std * LastSTD, OrderPrice - long_gap)
        #　移動式停損5%
        history_max = max(history_max, ThisClose)
        Condition4 = (history_max * 0.95) >= ThisClose
        
        if LastLow < out or Condition4:
          # 平倉日期
          CoverDate = NextDate
          # 平倉時間
          CoverTime = NextTime
          # 平倉價格
          CoverPrice = NextOpen
          # 把交易紀錄寫進Record.csv
          Record.write(
              ",".join(
                  [Prod, "S", str(CoverDate), str(CoverTime), str(CoverPrice), str(QTY) + "\n"]
              )
          )
          BS = None
          Capital = Capital + QTY * 1000 * CoverPrice - CoverPrice*0.001425     # 計算剩餘資金
          QTY = 0  
          history_max = 0

Record.close()
print('Done.')
