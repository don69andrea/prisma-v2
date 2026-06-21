"""
PRISMA V3.5 — Machbarkeits-PoC
Beweist zwei Dinge auf echten Gratis-Daten (yfinance, BTC/ETH täglich):

  (A) VOLATILITÄT ist vorhersagbar  -> echtes positives ML-Ziel (anders als Returns)
  (B) TREND-FOLLOWING + VOL-TARGETING liefert einen ehrlichen, OOS-robusten
      risiko-adjustierten Vorteil ggü. Buy&Hold UND exposure-matched Baseline
      (genau der Test, an dem das alte Return-ML scheiterte).

Methodik bewusst streng:
  - keine Parameter-Optimierung (alle a priori fixiert) -> kein Overfitting
  - Signale nur aus Vergangenheit (shift), kein Look-Ahead
  - Netto nach Transaktionskosten
  - exposure-matched Baseline isoliert echten Timing-Skill von blosser Unterinvestition
"""
import numpy as np, pandas as pd

COST = 0.001          # 0.1% pro Handelsvolumen-Einheit (Krypto realistisch, eher konservativ)
ANN  = 365            # Krypto handelt 365 Tage
TARGET_VOL = 0.60     # 60% annualisierte Ziel-Vol fürs Sizing
VOL_LB = 20           # Vol-Schätzfenster (Tage)
TREND_LB = 100        # Trend-Fenster (Tage) — a priori, NICHT optimiert

def sharpe(r):  return np.sqrt(ANN)*r.mean()/r.std() if r.std()>0 else 0
def cagr(r):    return (1+r).prod()**(ANN/len(r))-1
def maxdd(r):
    eq=(1+r).cumprod(); return (eq/eq.cummax()-1).min()
def calmar(r):
    dd=maxdd(r); return cagr(r)/abs(dd) if dd<0 else np.nan

def load(sym):
    df=pd.read_csv(f'{sym}.csv', skiprows=[1,2], header=0)
    df=df.rename(columns={'Price':'Date'})
    df['Date']=pd.to_datetime(df['Date']); df=df.set_index('Date')
    for c in df.columns: df[c]=pd.to_numeric(df[c], errors='coerce')
    df['ret']=df['Close'].pct_change()
    return df.dropna()

# ---------- (A) VOL-FORECAST: ist Vol lernbar? ----------
def vol_forecast_test(df, sym):
    r=df['ret']
    # Ziel: realisierte Vol der NÄCHSTEN 20 Tage (annualisiert), sauber forward-ausgerichtet:
    # rolling(20).std() an t+20 deckt Returns t+1..t+20 ab -> shift(-20) bringt es auf t
    fwd_vol=r.rolling(20).std().shift(-20)*np.sqrt(ANN)
    # HAR-style Features: Vol über 1/5/20/60 Tage (nur Vergangenheit)
    X=pd.DataFrame({
        'v5':  r.rolling(5).std()*np.sqrt(ANN),
        'v20': r.rolling(20).std()*np.sqrt(ANN),
        'v60': r.rolling(60).std()*np.sqrt(ANN),
        'absret': r.abs().rolling(5).mean()*np.sqrt(ANN),
    })
    data=pd.concat([X, fwd_vol.rename('y')],axis=1).dropna()
    n=len(data); split=int(n*0.6)          # expanding: train auf ersten 60%, OOS auf Rest
    from numpy.linalg import lstsq
    tr,te=data.iloc[:split],data.iloc[split:]
    A=np.c_[np.ones(len(tr)), tr[['v5','v20','v60','absret']].values]
    beta,*_=lstsq(A, tr['y'].values, rcond=None)
    Ate=np.c_[np.ones(len(te)), te[['v5','v20','v60','absret']].values]
    pred=Ate@beta
    y=te['y'].values
    # Baseline: konstante Vol = Mittel des Trainingszeitraums
    base=np.full_like(y, tr['y'].mean())
    ss_res=((y-pred)**2).sum(); ss_base=((y-base)**2).sum()
    r2_oos=1-ss_res/ss_base                 # OOS-R² ggü. konstanter Baseline
    # naive Persistenz-Baseline (v20 als Prognose)
    naive=te['v20'].values; ss_naive=((y-naive)**2).sum()
    r2_vs_naive=1-ss_res/ss_naive
    corr=np.corrcoef(pred,y)[0,1]
    return dict(sym=sym, r2_oos=r2_oos, r2_vs_naive=r2_vs_naive, corr=corr, n_oos=len(te))

# ---------- (B) TREND-FOLLOWING + VOL-TARGETING ----------
def trend_strategy(df, sym):
    r=df['ret']
    px=df['Close']
    # Signal: Preis über 100-Tage-Schnitt? (klassisches TS-Momentum) — nur Vergangenheit
    sig=(px>px.rolling(TREND_LB).mean()).astype(float).shift(1)
    # Vol-Targeting-Skalierung (Risiko konstant halten)
    vol=r.rolling(VOL_LB).std()*np.sqrt(ANN)
    scale=(TARGET_VOL/vol).clip(upper=1.5).shift(1)      # Cap 1.5x Hebel
    expo=(sig*scale).fillna(0).clip(0,1.5)               # long-only, 0..1.5
    turn=expo.diff().abs().fillna(0)
    strat=expo*r - turn*COST                             # netto nach Kosten
    # exposure-matched Baseline: konstante Investitionsquote = Ø-Exposure der Strategie
    avg_expo=expo.mean()
    em=avg_expo*r - 0*COST                               # konstant -> ~kein Turnover
    bh=r.copy()
    common=strat.dropna().index
    return expo, strat.loc[common], em.loc[common], bh.loc[common]

def report(name, r):
    return f"{name:22s} CAGR {cagr(r)*100:6.1f}%  Sharpe {sharpe(r):5.2f}  MaxDD {maxdd(r)*100:6.1f}%  Calmar {calmar(r):5.2f}"

print("="*78)
print("PRISMA V3.5 — MACHBARKEITS-PoC  (echte yfinance-Daten, täglich)")
print("="*78)

for sym in ['BTC-USD','ETH-USD']:
    df=load(sym)
    print(f"\n### {sym}  | {df.index.min().date()} .. {df.index.max().date()}  (N={len(df)})")

    # (A)
    vf=vol_forecast_test(df, sym)
    print(f"(A) VOL-FORECAST (OOS, {vf['n_oos']} Tage):")
    print(f"    OOS-R² vs konstante Baseline : {vf['r2_oos']*100:5.1f}%   "
          f"(>0 = Vol IST lernbar)")
    print(f"    OOS-R² vs naive Persistenz   : {vf['r2_vs_naive']*100:5.1f}%")
    print(f"    Korrelation Prognose/Realität: {vf['corr']:.2f}")

    # (B)
    expo,strat,em,bh=trend_strategy(df, sym)
    print(f"(B) TREND-FOLLOWING + VOL-TARGETING (Ø-Exposure {expo.mean()*100:.0f}%):")
    print("    "+report("Strategie (netto)", strat))
    print("    "+report("Exposure-Matched", em))
    print("    "+report("Buy & Hold", bh))

    # Per-Jahr OOS-Stabilität der Strategie vs Buy&Hold (Sharpe)
    yr=pd.DataFrame({'strat':strat,'bh':bh})
    g=yr.groupby(yr.index.year).apply(lambda d: pd.Series(
        {'strat_Sharpe':sharpe(d['strat']),'bh_Sharpe':sharpe(d['bh'])}))
    wins=(g['strat_Sharpe']>g['bh_Sharpe']).sum()
    print(f"    Jahres-Stabilität: Strategie-Sharpe > B&H-Sharpe in {wins}/{len(g)} Jahren")
print("\n"+"="*78)
