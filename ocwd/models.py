"""Detectors: the proposed excitation-coherent model and the baselines."""
from __future__ import annotations

import warnings

import numpy as np
import lightgbm as lgb
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

warnings.filterwarnings("ignore", category=UserWarning)

LGB_PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=20,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                  verbose=-1, n_jobs=4)


class GBM:
    """Supervised gradient-boosted trees (binary or multi-class)."""

    def __init__(self, features, multiclass=False, seed=0):
        self.features = list(features)
        self.multiclass = multiclass
        self.m = lgb.LGBMClassifier(random_state=seed, class_weight="balanced", **LGB_PARAMS)

    def fit(self, df, y):
        self.m.fit(df[self.features].to_numpy(np.float32), y)
        return self

    def score(self, df):
        p = self.m.predict_proba(df[self.features].to_numpy(np.float32))
        return p if self.multiclass else p[:, 1]

    def predict(self, df):
        return self.m.predict(df[self.features].to_numpy(np.float32))


class OneClass:
    """Unsupervised novelty detectors trained on healthy windows only."""

    def __init__(self, features, kind="iforest", seed=0):
        self.features = list(features)
        if kind == "iforest":
            self.m = IsolationForest(n_estimators=300, random_state=seed, n_jobs=4)
        else:
            self.m = make_pipeline(StandardScaler(), OneClassSVM(nu=0.05, gamma="scale"))

    def fit(self, df_healthy):
        X = df_healthy[self.features].to_numpy(np.float32)
        if len(X) > 4000 and isinstance(self.m, type(make_pipeline(StandardScaler()))):
            X = X[np.random.default_rng(0).choice(len(X), 4000, replace=False)]
        self.m.fit(X)
        return self

    def score(self, df):
        return -self.m.decision_function(df[self.features].to_numpy(np.float32))


class Threshold:
    """Single-statistic rule; the score is the statistic itself."""

    def __init__(self, feature):
        self.feature = feature

    def fit(self, *a, **k):
        return self

    def score(self, df):
        return df[self.feature].to_numpy(float)


class CoherenceTest:
    """Training-free test: a loss excess that is excitation-coherent.

    score = z-statistic of the Poisson slope of loss counts on excitation,
    gated by the presence of losses.  Needs no labels and no healthy data from
    the target vehicle."""

    def __init__(self, z="coh_z", loss="miss_pm"):
        self.z, self.loss = z, loss

    def fit(self, *a, **k):
        return self

    def score(self, df):
        return df[self.z].to_numpy(float) + 0.01 * np.log1p(df[self.loss].to_numpy(float))


# ---------------------------------------------------------------------------
# Deep sequence baselines (PyTorch, CPU)
# ---------------------------------------------------------------------------
def _torch():
    import torch
    torch.set_num_threads(4)
    return torch


class SeqCNN:
    """Supervised 1-D CNN on the binned telemetry sequence."""

    def __init__(self, n_in, n_out=2, seed=0, epochs=15):
        torch = _torch()
        torch.manual_seed(seed)
        nn = torch.nn
        self.net = nn.Sequential(
            nn.Conv1d(n_in, 32, 7, padding=3), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(32, 64, 5, padding=2), nn.ReLU(), nn.MaxPool1d(2),
            nn.Conv1d(64, 64, 3, padding=1), nn.ReLU(), nn.AdaptiveMaxPool1d(1), nn.Flatten(),
            nn.Linear(64, n_out))
        self.epochs, self.n_out = epochs, n_out

    def fit(self, X, y):
        torch = _torch()
        self.mu = X.mean(axis=(0, 2), keepdims=True)
        self.sd = X.std(axis=(0, 2), keepdims=True) + 1e-6
        Xt = torch.tensor((X - self.mu) / self.sd, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        w = np.bincount(y, minlength=self.n_out).astype(float)
        w = torch.tensor(w.sum() / (w + 1) / self.n_out, dtype=torch.float32)
        opt = torch.optim.Adam(self.net.parameters(), 1e-3)
        lossf = torch.nn.CrossEntropyLoss(weight=w)
        g = torch.Generator().manual_seed(0)
        for _ in range(self.epochs):
            perm = torch.randperm(len(Xt), generator=g)
            for i in range(0, len(Xt), 128):
                b = perm[i:i + 128]
                opt.zero_grad()
                lossf(self.net(Xt[b]), yt[b]).backward()
                opt.step()
        return self

    def proba(self, X):
        torch = _torch()
        with torch.no_grad():
            out = []
            Xt = torch.tensor((X - self.mu) / self.sd, dtype=torch.float32)
            for i in range(0, len(Xt), 512):
                out.append(torch.softmax(self.net(Xt[i:i + 512]), 1).numpy())
        return np.concatenate(out)


class SeqTransformer(SeqCNN):
    """Supervised Transformer encoder on the binned telemetry sequence
    (temporal average pooling to at most 150 tokens, 2 layers, 4 heads)."""

    def __init__(self, n_in, n_out=2, seed=0, epochs=15, d=32, max_tokens=150):
        torch = _torch()
        torch.manual_seed(seed)
        nn = torch.nn
        self.max_tokens, self.n_out, self.epochs = max_tokens, n_out, epochs

        class Net(nn.Module):
            def __init__(s):
                super().__init__()
                s.emb = nn.Linear(n_in, d)
                s.pos = nn.Parameter(torch.zeros(1, max_tokens, d))
                layer = nn.TransformerEncoderLayer(d, 4, 2 * d, dropout=0.1, batch_first=True)
                s.enc = nn.TransformerEncoder(layer, 2)
                s.out = nn.Linear(d, n_out)

            def forward(s, x):                     # x: (n, C, T)
                T = x.shape[-1]
                if T > max_tokens:
                    k = int(np.ceil(T / max_tokens))
                    x = torch.nn.functional.avg_pool1d(x, k, k, ceil_mode=True)
                h = s.emb(x.transpose(1, 2))
                h = h + s.pos[:, : h.shape[1]]
                return s.out(s.enc(h).mean(1))

        self.net = Net()


class LSTMAE:
    """LSTM encoder-decoder anomaly detector (Malhotra et al. 2016) trained on
    healthy sequences; anomaly score = reconstruction error."""

    def __init__(self, n_in, seed=0, hidden=32, epochs=15):
        torch = _torch()
        torch.manual_seed(seed)
        nn = torch.nn

        class AE(nn.Module):
            def __init__(s):
                super().__init__()
                s.enc = nn.LSTM(n_in, hidden, batch_first=True)
                s.dec = nn.LSTM(hidden, hidden, batch_first=True)
                s.out = nn.Linear(hidden, n_in)

            def forward(s, x):
                _, (h, _) = s.enc(x)
                z = h[-1].unsqueeze(1).repeat(1, x.shape[1], 1)
                y, _ = s.dec(z)
                return s.out(y)

        self.net, self.epochs = AE(), epochs

    def fit(self, X):  # X: (n, C, T)
        torch = _torch()
        X = X.transpose(0, 2, 1)
        self.mu = X.mean(axis=(0, 1), keepdims=True)
        self.sd = X.std(axis=(0, 1), keepdims=True) + 1e-6
        Xt = torch.tensor((X - self.mu) / self.sd, dtype=torch.float32)
        opt = torch.optim.Adam(self.net.parameters(), 1e-3)
        g = torch.Generator().manual_seed(0)
        for _ in range(self.epochs):
            perm = torch.randperm(len(Xt), generator=g)
            for i in range(0, len(Xt), 64):
                b = Xt[perm[i:i + 64]]
                opt.zero_grad()
                ((self.net(b) - b) ** 2).mean().backward()
                opt.step()
        return self

    def score(self, X):
        torch = _torch()
        X = X.transpose(0, 2, 1)
        Xt = torch.tensor((X - self.mu) / self.sd, dtype=torch.float32)
        out = []
        with torch.no_grad():
            for i in range(0, len(Xt), 256):
                b = Xt[i:i + 256]
                out.append(((self.net(b) - b) ** 2).mean(axis=(1, 2)).numpy())
        return np.concatenate(out)


def binned_sequence(t, cid, t0, W, step=0.1):
    """(3, T) sequence: frames per bin, distinct IDs per bin, longest silence in bin."""
    T = int(round(W / step))
    m = (t >= t0) & (t < t0 + W)
    t, cid = t[m], cid[m]
    b = np.floor((t - t0) / step).astype(int).clip(0, T - 1)
    cnt = np.bincount(b, minlength=T).astype(np.float32)
    ids = np.zeros(T, np.float32)
    if len(b):
        key = np.unique(b * 4096 + (cid % 4096))
        ids = np.bincount(key // 4096, minlength=T).astype(np.float32)[:T]
    sil = np.zeros(T, np.float32)
    if len(t) > 1:
        tt = np.sort(t)
        d = np.diff(tt)
        np.maximum.at(sil, b[np.argsort(t, kind="stable")][1:], d.astype(np.float32))
    return np.stack([cnt, ids, sil])
