"""
PRISMA V4 — Indikator-Backtest (ehrlich, long/flat, netto Kosten)
Beantwortet datenbasiert: WELCHE Chart-Metriken helfen wirklich?

Regeln bewusst STANDARD & a priori (keine Optimierung):
  MA   : Close > SMA(100)                      (Trend)
  MACD : MACD(12,26) > Signal(9)               (Trend/Momentum)
  RSI  : RSI(14) > 50                           (Momentum-Filter)
  BOLL : Close > unteres Band & < oberem Band? -> als Trend: Close>Mittelband
  COMBO_TREND : MA UND MACD                      (Konsens Trend)
  COMBO_VOTE  : Mehrheit aus {MA, MACD, RSI>50}  (2 von 3)
Signal = long(1)/flat(0), 1 Tag verzögert (kein Look-Ahead). Kosten 0.1%/Umschichtung.
Vergleich: Buy&Hold + Exposure-Matched (gleiche Ø-Investitionsquote).
SELL bedeutet hier 'raus/cash' (long-only) — kein Shorting.
"""
import numpy as np, pandas as pd
ANN=365; COST=0.001

def load(s):
    d=pd.read_csv(f'{s}.csv',skiprows=[1,2]).rename(columns={'Price':'Date'})
    d['Date']=pd.to_datetime(d['Date']);d=d.set_index('Date')
    for c in d.columns:d[c]=pd.to_numeric(d[c],errors='coerce')
    d['ret']=d['Close'].pct_change();return d.dropna()

def rsi(s,n=14):
    d=s.diff();up=d.clip(lower=0).rolling(n).mean();dn=(-d.clip(upper=0)).rolling(n).mean()
    rs=up/dn.replace(0,np.nan);return 100-100/(1+rs)
def ema(s,n):return s.ewm(span=n,adjust=False).mean()

def signals(d):
    px=d['Close']
    sma100=px.rolling(100).mean()
    macd=ema(px,12)-ema(px,26); macd_sig=ema(macd,9)
    r=rsi(px,14)
    mid=px.rolling(20).mean()
    sig={}
    sig['MA']        =(px>sma100).astype(float)
    sig['MACD']      =(macd>macd_sig).astype(float)
    sig['RSI>50']    =(r>50).astype(float)
    sig['BOLL_mid']  =(px>mid).astype(float)
    sig['COMBO_TREND']=((px>sma100)&(macd>macd_sig)).astype(float)
    vote=( (px>sma100).astype(int)+(macd>macd_sig).astype(int)+(r>50).astype(int) )
    sig['COMBO_VOTE']=(vote>=2).astype(float)
    return sig

def metrics(r):
    r=r.dropna()
    eq=(1+r).cumprod();dd=(eq/eq.cummax()-1).min()
    cg=(1+r).prod()**(ANN/len(r))-1; sh=np.sqrt(ANN)*r.mean()/r.std() if r.std()>0 else 0
    return cg,sh,dd,(cg/abs(dd) if dd<0 else float('nan'))

for s in ['BTC-USD','ETH-USD']:
    d=load(s); r=d['ret']; sig=signals(d)
    print(f"\n{'='*70}\n{s}  N={len(d)}  ({d.index.min().date()}..{d.index.max().date()})\n{'='*70}")
    print(f"{'Strategie':14s}{'CAGR':>9}{'Sharpe':>8}{'MaxDD':>9}{'Calmar':>8}{'Expo':>7}{'>EM?':>6}")
    cg,sh,dd,ca=metrics(r)
    print(f"{'Buy&Hold':14s}{cg*100:8.1f}%{sh:8.2f}{dd*100:8.1f}%{ca:8.2f}{'100%':>7}{'--':>6}")
    for name,sg in sig.items():
        expo=sg.shift(1).fillna(0)
        turn=expo.diff().abs().fillna(0)
        strat=expo*r-turn*COST
        em=expo.mean()*r            # exposure-matched
        cg,sh,dd,ca=metrics(strat)
        _,she,_,cae=metrics(em.loc[strat.dropna().index])
        beat = (sh>she and (ca>cae if ca==ca and cae==cae else False))
        print(f"{name:14s}{cg*100:8.1f}%{sh:8.2f}{dd*100:8.1f}%{ca:8.2f}{expo.mean()*100:6.0f}%{('JA' if beat else 'nein'):>6}")
