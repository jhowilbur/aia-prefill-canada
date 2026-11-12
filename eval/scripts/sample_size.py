"""Sample-size numbers quoted in docs/eval-plan.md. Re-run: python3 -I eval/scripts/sample_size.py"""
from math import sqrt
def wilson(k,n,z=1.959964):
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/d; return c-h,c+h
print("Wilson 95% half-width at p=0.8 / 0.9:")
for n in (10,15,20,30,50,100,150,200,400):
    lo,hi=wilson(round(0.8*n),n); lo9,hi9=wilson(round(0.9*n),n)
    print(f" n={n:4d}  p=.8 -> [{lo:.3f},{hi:.3f}] hw={(hi-lo)/2:.3f}   p=.9 -> [{lo9:.3f},{hi9:.3f}]")
# smallest n so that observed 0.8 gives Wilson half-width <= 0.08
for target in (0.10,0.08,0.05):
    n=5
    while True:
        lo,hi=wilson(0.8*n,n)
        if (hi-lo)/2<=target: break
        n+=1
    print(f"n for half-width<={target} at p=.8: {n}")
# AIA-level: k of n agreement needed for Wilson lower >= 0.65
for n in (15,20,30,40):
    for k in range(n+1):
        if wilson(k,n)[0]>=0.65: print(f"level agreement: n={n} need k>={k} ({k/n:.2f}) for lower>=0.65"); break
for n in (15,20,30):
    for k in range(n+1):
        if wilson(k,n)[0]>=0.5: print(f"level agreement: n={n} need k>={k} ({k/n:.2f}) for lower>=0.50"); break
# Design effect for clustered items: deff = 1+(m-1)*icc
for m,icc in ((60,0.05),(60,0.1),(60,0.2)):
    print(f"deff m={m} icc={icc}: {1+(m-1)*icc:.1f}  -> 30 AIAs x {m} items = {30*m} items ~ {30*m/(1+(m-1)*icc):.0f} effective")
# human labelling time
items=100+50+15+30
print("human items",items,"at 1.5 min ->",items*1.5/60,"h; at 1.0 ->",items/60,"h; at 2.0 ->",items*2/60,"h")
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np, metrics as M
rng = np.random.default_rng(0)
for n in (40, 100, 150, 300, 1000):
    c = rng.uniform(0.6, 1.0, n)
    nb = M.default_n_bins(n)
    print(f"null ECE 95th pct, perfectly calibrated, conf~U(.6,1), n={n}, bins={nb}: {M.null_ece_quantile(c, nb, seed=1):.3f}")
# ---- v1.1 additions (real counts from eval/scripts/set_counts.py) ----
print("v1.1: Wilson intervals for the reset gates")
for k,n,label in ((77,90,"C-ext evidence items, p=.85, n=90"),(85,100,"H1 p=.85 n=100"),(21,30,"unanswerable items, p=.70, n=30"),
                  (20,25,"per-question n=25 (CV AIAs), p=.80"),(6,7,"lock-box 6/7"),(17,25,"majority level CV 17/25"),(19,32,"majority level JSON 19/32")):
    lo,hi=wilson(k,n); print(f" {label}: {k}/{n}={k/n:.3f} -> [{lo:.3f},{hi:.3f}]")
for m,icc in ((40,0.05),(40,0.1),(40,0.2)):
    print(f"deff m={m} icc={icc}: {1+(m-1)*icc:.1f} -> 25 AIAs x {m} = {25*m} items ~ {25*m/(1+(m-1)*icc):.0f} effective; 12 AIAs ~ {12*m/(1+(m-1)*icc):.0f}")
# ---- v1.1b additions (H1 redesign: Gate B evidence items from C-narr only) ----
print("v1.1b: H1 / B4 sample size on C-narr")
for n in (60, 80, 100, 120, 150):
    kmin = next(k for k in range(n + 1) if wilson(k, n)[0] >= 0.60)
    print(f" B4 n={n}: need k>={kmin} ({kmin/n:.3f}) for Wilson lower >= 0.60; p=.8 half-width {(wilson(round(.8*n),n)[1]-wilson(round(.8*n),n)[0])/2:.3f}")
for p in (0.70, 0.75, 0.80):
    n = 5
    while wilson(p * n, n)[0] < 0.60: n += 1
    print(f" smallest n with Wilson lower >= 0.60 when observed p={p:.2f}: {n}")
for icc in (0.05, 0.1, 0.2):
    d = 1 + (8 - 1) * icc
    print(f" H1 cluster cap m=8, icc={icc}: deff {d:.2f} -> 100 items ~ {100/d:.0f} effective; C-narr CV pool capacity 25 AIAs x 8 = 200")
print(" C-ext capacity at <= 8 per AIA: 6 x 8 = 48 (optional, Gate C only)")
for label, it in (("H1-H3 judged items (150+15+30)", 195), ("optional C-ext extra", 48)):
    print(f" {label}: {it} items -> {it/60:.1f}-{it*2/60:.1f} h (1-2 min/item), {it*1.5/60:.1f} h at 1.5 min")
