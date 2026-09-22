"""Compare cluster candidates on a fixed embedding sample and coverage."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import duckdb
from sklearn.cluster import HDBSCAN, MiniBatchKMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "features"
fingerprint = (FEATURES / "fingerprint.txt").read_text().strip()
projection = np.load(FEATURES / f"projection-nonempty-{fingerprint[:12]}.npz")
reduced = projection["reduced"]
embedding = np.load(FEATURES / "embeddings.npy")
cached = pd.read_parquet(FEATURES / "chunks.parquet")
with duckdb.connect(str(ROOT / "data" / "analytics.duckdb"), read_only=True) as db:
    valid_ids = {row[0] for row in db.execute("select chunk_id from raw.chunks").fetchall()}
mask = cached.chunk_id.isin(valid_ids).to_numpy()
embedding = embedding[mask]
assert len(reduced) == len(embedding)
rng = np.random.default_rng(42)
sample = np.sort(rng.choice(len(embedding), 2400, replace=False))
sample_embedding = normalize(embedding[sample])


def score(name, labels):
    counts = Counter(labels[labels >= 0])
    selected = labels[sample]
    in_cluster = selected >= 0
    if len(counts) < 2 or len(np.unique(selected[in_cluster])) < 2:
        return None
    silhouette = silhouette_score(
        sample_embedding[in_cluster], selected[in_cluster], metric="cosine",
    )
    coverage = float(np.mean(labels >= 0))
    biggest = max(counts.values()) / len(labels)
    return {
        "name": name,
        "clusters": len(counts),
        "coverage": round(coverage, 4),
        "largest_share": round(biggest, 4),
        "silhouette_cosine_original": round(float(silhouette), 4),
        "score": round(float(silhouette) * coverage * (1 - biggest), 4),
        "labels": labels,
    }


results = []
for selection in ("eom", "leaf"):
    for size in (80, 120, 180, 250):
        for samples in (5, 15):
            labels = HDBSCAN(
                min_cluster_size=size,
                min_samples=samples,
                cluster_selection_method=selection,
                n_jobs=6,
            ).fit_predict(reduced)
            result = score(f"hdbscan_{selection}_{size}_{samples}", labels)
            if result:
                results.append(result)
                print({k: v for k, v in result.items() if k != "labels"}, flush=True)
for k in (16, 20, 24, 30, 36):
    labels = MiniBatchKMeans(
        n_clusters=k, random_state=42, n_init=5, batch_size=2048,
    ).fit_predict(embedding)
    result = score(f"kmeans_{k}", labels)
    results.append(result)
    print({key: value for key, value in result.items() if key != "labels"}, flush=True)
for result in results:
    result.pop("labels")
(FEATURES / "cluster_search.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8",
)
