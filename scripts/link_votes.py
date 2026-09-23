"""Find thematically similar debate speeches for voted decision points.

Similarity is not a stance detector. The link has no implication that a speaker
endorsed or opposed the decision, and is deliberately stored separately from
the exact member votes and motion references.
"""
import os
os.environ['USE_TF'] = '0'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


def main():
    with duckdb.connect(str(DATA / 'analytics.duckdb')) as db:
        decisions = db.execute('select d.vote_id,d.session,coalesce(d.title,\'\') as title,coalesce(d.point_heading,\'\') as point_heading,min(v.vote_date) as vote_date from stg_decisions d join stg_votes v on d.vote_id=v.vote_id group by 1,2,3,4 order by 1').df()
        speeches = db.execute('select speech_id,session,party,speech_date,speaker,original_person_id from stg_speeches where eligible').df()
        vote_members = db.execute('select distinct vote_id,party,member_id from stg_votes where party in (\'S\',\'M\',\'V\',\'MP\',\'C\',\'L\',\'KD\',\'SD\')').df()
        if decisions.empty:
            db.execute('create or replace table raw.decision_speech_links as select cast(null as varchar) as vote_id,cast(null as varchar) as party,cast(null as varchar) as speech_id,cast(null as double) as cosine_similarity,cast(null as boolean) as same_member where false')
            return
    cached = pd.read_parquet(DATA / 'features' / 'chunks.parquet')
    embedding = np.load(DATA / 'features' / 'embeddings.npy')
    keep = (cached.word_count.to_numpy() > 0) & cached.speech_id.isin(set(speeches.speech_id)).to_numpy()
    cached, embedding = cached.loc[keep].reset_index(drop=True), embedding[keep]
    ids = cached.speech_id.unique()
    groups = cached.groupby('speech_id', sort=False).indices
    speech_vectors = np.vstack([
        np.average(embedding[groups[s]], axis=0,
                   weights=np.maximum(cached.iloc[groups[s]].word_count.to_numpy(), 1))
        for s in ids
    ]).astype(np.float32)
    speech_vectors /= np.linalg.norm(speech_vectors, axis=1, keepdims=True)
    model = SentenceTransformer(MODEL, local_files_only=True)
    texts = (decisions.title + '. ' + decisions.point_heading).tolist()
    decision_vectors = model.encode(texts, batch_size=64, normalize_embeddings=True,
                                    show_progress_bar=False)
    speech_meta = speeches.set_index('speech_id').loc[ids]
    member_lookup = vote_members.groupby(['vote_id','party']).member_id.agg(set).to_dict()
    links = []
    for i, decision in enumerate(decisions.itertuples()):
        # Only previous speeches in the same parliamentary session are candidates.
        available = (speech_meta.session.to_numpy() == decision.session)
        if pd.notna(decision.vote_date):
            available &= (speech_meta.speech_date.to_numpy() <= decision.vote_date)
        scores = speech_vectors @ decision_vectors[i]
        for party in sorted(set(vote_members.loc[vote_members.vote_id == decision.vote_id, 'party'])):
            candidates = np.flatnonzero(available & (speech_meta.party.to_numpy() == party))
            if not len(candidates):
                continue
            best = candidates[np.argmax(scores[candidates])]
            if scores[best] < 0.6:
                continue
            sid = ids[best]
            links.append({
                'vote_id': decision.vote_id, 'party': party, 'speech_id': sid,
                'cosine_similarity': float(scores[best]),
                'same_member': str(speech_meta.iloc[best].original_person_id) in member_lookup.get((decision.vote_id, party), set()),
            })
    frame = pd.DataFrame(links, columns=['vote_id','party','speech_id','cosine_similarity','same_member'])
    with duckdb.connect(str(DATA / 'analytics.duckdb')) as db:
        db.register('link_frame', frame)
        db.execute('create or replace table raw.decision_speech_links as select * from link_frame')
    print(f'{len(frame)} tematiska länkar till tidigare tal; inga ståndpunkter har infererats')


if __name__ == '__main__':
    main()
