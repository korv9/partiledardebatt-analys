"""Local, cached NLP features. SQL transformations live in the dbt models."""
import os
os.environ['USE_TF'] = '0'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
from pathlib import Path
_numba_cache = Path(__file__).resolve().parents[1] / 'data' / 'numba_cache'
_numba_cache.mkdir(parents=True, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = str(_numba_cache)
import hashlib
import json
import re
import sqlite3
from collections import Counter
import duckdb
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.cluster import HDBSCAN, MiniBatchKMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sentence_transformers import SentenceTransformer
import torch
from umap import UMAP

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
STOP = set('och i att det som en på är av för med till den har de inte om ett men vi jag så han hon man sig var från kan när också ska skulle under eller detta blir vara varit finns dem dess dessa där här hur vad då nu än efter före över upp ut in oss ni du dig mig sin sina sitt vår våra er era vilket vilken vilka genom mot mellan alla allt mycket mer mest fler flera något någon några bara hade ha fick får få vill ville kommer kom kunde måste bör behöver hela helt både samma sedan utan hos därför eftersom kanske alltså ju väl även samt sådan sådana dessa denna detta talman herr fru tack applåder anf anförande replik fråga frågan frågor svar svara säger säga sade sa tycker tror gör göra gjort gäller delen del sätt dag idag år gången gång verkligen faktiskt naturligtvis väldigt exempel exempelvis gäller människor sverige svenska svensk land landet länder riksdagen regering regeringen regerings ska skall många andra politik politiken parti partiet statsministern bra ser kunna handlar står fram nya stora vet bättre vårt bli just tid'.split())


def tokens(text):
    return re.findall(r'[a-zåäöéü]+(?:-[a-zåäöéü]+)*', text.casefold())


def clean_text(text):
    text = text.replace('\xad', '').replace('\u200b', '')
    return re.sub(r'(?im)^\s*STYLEREF[^\n]*(?:\n|$)', '\n', text)


def name(raw):
    raw = re.sub(r'\s+(?:replik|anförande)\s*$', '', raw, flags=re.I)
    raw = re.sub(r'\s*\([^)]*\)\s*$', '', raw).strip()
    if 'talman' in raw.casefold():
        return 'Talmannen'
    raw = re.sub(r'^.*?(?:ministern?|statsrådet)\s+', '', raw, flags=re.I)
    return ' '.join(raw.split()).title()


def main():
    torch.set_num_threads(6)
    cache = DATA / 'features'
    cache.mkdir(exist_ok=True)
    with sqlite3.connect(DATA / 'debates.sqlite') as conn:
        speeches = pd.read_sql_query('select * from speeches order by dok_id, cast(anforande_nummer as int)', conn)
    speeches['speech_id'] = speeches.dok_id + '-' + speeches.anforande_nummer
    speeches['speaker'] = speeches.talare.map(name)
    speeches['party'] = speeches.parti.str.upper().replace({'FP': 'L', 'KDS': 'KD'})
    speeches['analysis_text'] = speeches.anforandetext.map(clean_text)
    speeches['word_count'] = speeches.analysis_text.map(lambda t: len(tokens(t)))
    speeches['eligible'] = (speeches.speaker != 'Talmannen') & speeches.party.isin(['S','M','V','MP','C','L','KD','SD','NYD']) & (speeches.word_count >= 20)
    fingerprint = hashlib.sha256((MODEL + '|tokens120-v3-clean-fields|' + ''.join(speeches.speech_id + speeches.analysis_text)).encode()).hexdigest()
    print('Loading local multilingual model', flush=True)
    model = SentenceTransformer(MODEL, local_files_only=True, device='cuda' if torch.cuda.is_available() else 'cpu')
    model.max_seq_length = 128
    if (cache / 'fingerprint.txt').exists() and (cache / 'fingerprint.txt').read_text() == fingerprint:
        chunks = pd.read_parquet(cache / 'chunks.parquet')
        emb = np.load(cache / 'embeddings.npy')
    else:
        rows = []
        for speech in speeches[speeches.eligible].itertuples():
            text = re.sub(r'\([^)]*(?:applåder|skratt)[^)]*\)', '', speech.analysis_text, flags=re.I)
            text = re.sub(r'\b(?:herr|fru)\s+talman\b[!.,:]?', '', text, flags=re.I).strip()
            offsets = model.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)['offset_mapping']
            for start in range(0, len(offsets), 120):
                end = min(start + 120, len(offsets))
                part = text[offsets[start][0]:offsets[end-1][1]]
                rows.append({'chunk_id': f'{speech.speech_id}:{start//120}', 'speech_id': speech.speech_id,
                             'chunk_index': start//120, 'text': part, 'word_count': len(tokens(part)),
                             'model_tokens': end-start})
        chunks = pd.DataFrame(rows)
        print(f'Encoding {len(chunks)} text segments on {model.device}', flush=True)
        emb = np.zeros((len(chunks),384),dtype=np.float32)
        missing = list(range(len(chunks)))
        prior_metrics = json.loads((cache/'metrics.json').read_text()) if (cache/'metrics.json').exists() else {}
        if prior_metrics.get('model') == MODEL and (cache/'chunks.parquet').exists() and (cache/'embeddings.npy').exists():
            old_chunks = pd.read_parquet(cache/'chunks.parquet')
            old_emb = np.load(cache/'embeddings.npy')
            old_lookup = {text:i for i,text in enumerate(old_chunks.text)}
            missing=[]
            for i,text in enumerate(chunks.text):
                if text in old_lookup:emb[i]=old_emb[old_lookup[text]]
                else:missing.append(i)
        print(f'{len(missing)} new segments; exact-text cache used for the rest',flush=True)
        if missing:
            emb[missing] = model.encode(chunks.iloc[missing].text.tolist(), batch_size=96, normalize_embeddings=True, show_progress_bar=True)
        chunks.to_parquet(cache / 'chunks.parquet', index=False)
        np.save(cache / 'embeddings.npy', emb)
        (cache / 'fingerprint.txt').write_text(fingerprint)
    eligible_ids = set(speeches.loc[speeches.eligible, 'speech_id'])
    valid = (chunks.word_count.to_numpy() > 0) & chunks.speech_id.isin(eligible_ids).to_numpy()
    chunks = chunks.loc[valid].reset_index(drop=True)
    emb = emb[valid]
    print(f'UMAP 10D and density clustering: {len(chunks)} nonempty segments', flush=True)
    projection_path = cache / f'projection-nonempty-{fingerprint[:12]}.npz'
    if projection_path.exists() and np.load(projection_path)['reduced'].shape[0] == len(chunks):
        saved = np.load(projection_path)
        reduced, xy = saved['reduced'], saved['xy']
    else:
        reduced = UMAP(n_components=10, n_neighbors=30, min_dist=0.0, metric='cosine', random_state=42, n_epochs=150).fit_transform(emb)
        xy = UMAP(n_components=2, n_neighbors=30, min_dist=0.15, random_state=42, n_epochs=150).fit_transform(reduced)
        np.savez(projection_path, reduced=reduced, xy=xy)
    clusterer = HDBSCAN(min_cluster_size=250, min_samples=5,
                        cluster_selection_method='leaf', n_jobs=6)
    labels = clusterer.fit_predict(reduced)
    counts = Counter(labels[labels >= 0])
    method = 'HDBSCAN leaf (min_cluster_size=250, min_samples=5) on UMAP 10D'
    # A single giant density cluster is not a useful topic taxonomy. Explicit fallback.
    if len(counts) < 8 or max(counts.values(), default=0) > len(chunks)*0.5:
        method = 'KMeans 24 topics on original normalized embeddings; HDBSCAN rejected as too coarse'
        labels = MiniBatchKMeans(n_clusters=24, random_state=42, n_init=10, batch_size=2048).fit_predict(emb)
        alternate = MiniBatchKMeans(n_clusters=24, random_state=17, n_init=10, batch_size=2048).fit_predict(emb)
        stability = adjusted_rand_score(labels, alternate)
    else:
        alternate = HDBSCAN(min_cluster_size=260, min_samples=5,
                            cluster_selection_method='leaf', n_jobs=6).fit_predict(reduced)
        # Very short tail fragments form a density island without a substantive topic.
        short_clusters = {int(t) for t in set(labels) if t >= 0
                          and chunks.loc[labels == t, 'word_count'].mean() < 20}
        for t in short_clusters:
            labels[labels == t] = -1
        alternate_short = {int(t) for t in set(alternate) if t >= 0
                           and chunks.loc[alternate == t, 'word_count'].mean() < 20}
        for t in alternate_short:
            alternate[alternate == t] = -1
        stability = adjusted_rand_score(labels, alternate)
    metric_sample = np.sort(np.random.default_rng(42).choice(len(emb), min(2400, len(emb)), replace=False))
    sample_labels = labels[metric_sample]
    selected = sample_labels >= 0
    silhouette = (silhouette_score(emb[metric_sample][selected], sample_labels[selected], metric='cosine')
                  if len(set(sample_labels[selected])) > 1 else None)
    largest_share = max((count / len(labels) for count in Counter(labels[labels >= 0]).values()), default=0)
    chunks['topic_id'] = labels
    chunks['x'], chunks['y'] = xy[:,0], xy[:,1]
    speaker_words = {w for person in speeches.speaker.unique() for w in tokens(person)}
    label_stop = STOP | speaker_words | {
        'socialdemokraterna','moderaterna','vänsterpartiet','miljöpartiet',
        'centerpartiet','liberalerna','folkpartiet','kristdemokraterna',
        'sverigedemokraterna','ta','se','går','gå','gör','lite','min',
        'sveriges','s','sd','dom'
    }
    vectorizer = CountVectorizer(tokenizer=tokens, token_pattern=None, stop_words=sorted(label_stop), min_df=20, max_df=0.6, ngram_range=(1,2), max_features=18000)
    matrix = vectorizer.fit_transform(chunks.text)
    terms = vectorizer.get_feature_names_out()
    ids = sorted(set(labels))
    grouped = np.vstack([np.asarray(matrix[labels == t].sum(axis=0)).ravel() for t in ids])
    weights = TfidfTransformer().fit_transform(grouped).toarray()
    topic_rows = []
    for i, t in enumerate(ids):
        top = terms[np.argsort(weights[i])[-10:][::-1]].tolist()
        topic_rows.append({'topic_id': int(t), 'label': ' / '.join(top[:3]) if t >= 0 else 'Ej grupperade', 'keywords': ', '.join(top), 'chunks': int((labels == t).sum())})
    topics = pd.DataFrame(topic_rows)
    print(topics[['topic_id','label','chunks']].to_string(index=False), flush=True)
    # Word counts preserve surface forms. Denominators include stopwords.
    word_rows = []
    for speech in speeches[speeches.eligible].itertuples():
        for token, count in Counter(w for w in tokens(speech.analysis_text) if len(w)>2 and w not in label_stop).items():
            word_rows.append((speech.speech_id, token, count))
    words = pd.DataFrame(word_rows, columns=['speech_id','word','occurrences'])
    # Conservative exact-name dictionary: names with >=5 speeches; no surname-only guesses.
    people = speeches[speeches.eligible].speaker.value_counts()
    people = [p for p,n in people.items() if n>=5 and ' ' in p]
    parties = {'S':r'socialdemokrat\w*', 'M':r'moderat\w*', 'V':r'vänsterpart\w*', 'MP':r'miljöpart\w*',
               'C':r'centerpart\w*', 'L':r'folkpart\w*|liberalerna', 'KD':r'kristdemokrat\w*', 'SD':r'sverigedemokrat\w*', 'NYD':r'ny demokrati'}
    patterns = [(p,'person',re.compile(r'\b'+re.escape(p)+r'\b',re.I)) for p in people]
    patterns += [(p,'party',re.compile(r'\b(?:'+pat+r')\b',re.I)) for p,pat in parties.items()]
    mentions = []
    for speech in speeches[speeches.eligible].itertuples():
        for target, kind, pattern in patterns:
            hits = len(pattern.findall(speech.analysis_text))
            if hits:
                mentions.append((speech.speech_id,target,kind,hits,target == (speech.speaker if kind=='person' else speech.party)))
    mentions = pd.DataFrame(mentions,columns=['speech_id','target','kind','occurrences','self_mention'])
    # Speech vectors are word-weighted means of chunks; similarity in original space, never 2D.
    speech_ids = chunks.speech_id.unique()
    indexes = chunks.groupby('speech_id',sort=False).indices
    speech_emb = np.vstack([np.average(emb[indexes[s]],axis=0,weights=np.maximum(chunks.iloc[indexes[s]].word_count,1)) for s in speech_ids])
    speech_emb /= np.linalg.norm(speech_emb,axis=1,keepdims=True)
    distances, neighbors = NearestNeighbors(n_neighbors=12,metric='cosine',n_jobs=6).fit(speech_emb).kneighbors(speech_emb)
    meta = speeches.set_index('speech_id')
    similar=[]
    for i,sid in enumerate(speech_ids):
        kept=0
        for distance,j in zip(distances[i],neighbors[i]):
            target=speech_ids[j]
            if sid==target or meta.loc[sid,'speaker']==meta.loc[target,'speaker']:
                continue
            similar.append((sid,target,float(1-distance)))
            kept+=1
            if kept==3:break
    similar=pd.DataFrame(similar,columns=['speech_id','neighbor_id','cosine_similarity'])
    with duckdb.connect(str(DATA / 'analytics.duckdb')) as db:
        db.execute('begin transaction')
        db.execute('create schema if not exists raw')
        # Keep a fresh checkout buildable before the optional vote importer runs.
        db.execute('create table if not exists raw.votes (vote_id varchar, session varchar, designation varchar, point varchar, member_name varchar, member_id varchar, party varchar, vote varchar, subject varchar, vote_date varchar)')
        db.execute('create table if not exists raw.decisions (vote_id varchar, session varchar, document_id varchar, designation varchar, point varchar, title varchar, point_heading varchar, proposal_text varchar, winning_side varchar, decision_date varchar, source_url varchar, status_url varchar)')
        db.execute('create table if not exists raw.decision_motions (vote_id varchar, motion_id varchar, motion_reference varchar, motion_title varchar, motion_author varchar, motion_url varchar)')
        db.execute('create table if not exists raw.decision_speech_links (vote_id varchar, party varchar, speech_id varchar, cosine_similarity double, same_member boolean)')
        for table,frame in [('speeches',speeches),('chunks',chunks),('topics',topics),('words',words),('mentions',mentions),('similarities',similar)]:
            db.register('frame',frame)
            db.execute(f'create or replace table raw.{table} as select * from frame')
            db.unregister('frame')
        db.execute('commit')
    metrics={'model':MODEL,'fingerprint':fingerprint,'speech_count':len(speeches),'eligible_speeches':int(speeches.eligible.sum()),
             'segments':len(chunks),'clustering':method,'topics':len(set(labels)-{-1}),'unclustered_share':float(np.mean(labels==-1)),
             'largest_cluster_share':float(largest_share),
             'silhouette_cosine_original_sample':float(silhouette) if silhouette is not None else None,
             'evaluation_sample_size':len(metric_sample),
             'sensitivity_ARI':float(stability),'seed':42,'chunk_max_tokens':120,
             'short_fragment_clusters_excluded':len(short_clusters) if method.startswith('HDBSCAN') else 0,
             'note':'Silhouette is measured in the original embedding space on a fixed 2400-segment sample, excluding noise. ARI compares nearby HDBSCAN settings on the same UMAP projection; neither proves semantic validity.'}
    (cache/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':main()
