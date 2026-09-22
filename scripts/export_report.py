"""Export dbt marts to a self-contained interactive analysis report."""
from pathlib import Path
import json
import argparse
import duckdb
import numpy as np
from plotly.offline import get_plotlyjs

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--inline-output',help='Optional path for an in-conversation visualization')
    args=parser.parse_args()
    out=ROOT/'reports'
    out.mkdir(exist_ok=True)
    db=duckdb.connect(str(ROOT/'data/analytics.duckdb'),read_only=True)
    def records(sql):
        return json.loads(db.execute(sql).df().to_json(orient='records',date_format='iso',force_ascii=False))
    payload={
        'metrics':json.loads((ROOT/'data/features/metrics.json').read_text()),
        'topics':records('select * from mart_topics order by words desc'),
        'trends':records('select * from mart_topic_trends'),
        'speakerTopics':records('select * from mart_speaker_topics'),
        'words':records('select * from mart_word_usage where word in (select word from mart_word_usage where occurrences>=20 qualify row_number() over(partition by party order by occurrences desc)<=80 or row_number() over(partition by party order by log_rate_ratio desc)<=40)'),
        'speakerWords':records('select * from mart_speaker_words where occurrences>=10 qualify row_number() over(partition by speaker,party order by occurrences desc)<=40'),
        'mentions':records('select * from mart_mentions where not self_mention'),
        'speakers':records('select speaker,party,count(*) as speeches,sum(word_count) as words from stg_speeches where eligible group by speaker,party order by words desc'),
        'similar':records("select speech_id,neighbor_id,cosine_similarity,speaker,party,cast(speech_date as varchar) as speech_date,source_url,neighbor_speaker,neighbor_party,cast(neighbor_date as varchar) as neighbor_date,neighbor_url,substr(speech_text,1,700) as text,substr(neighbor_text,1,700) as neighbor_text from mart_similar_speeches where party<>neighbor_party and speech_id<neighbor_id order by cosine_similarity desc limit 150"),
        'points':records("select chunk_id,speech_id,topic_id,round(x,3) as x,round(y,3) as y,party,speaker,session_year,session,substr(text,1,500) as text,source_url from int_segments order by hash(chunk_id) limit 12000"),
        'coverage':records('select session,count(*) as speeches,count(distinct protocol_id) as protocols,sum(word_count) as words from stg_speeches where eligible group by session order by session'),
    }
    # Original embedding-space centroid examples, not chosen by the two-dimensional map.
    chunks=db.execute('select chunk_id,topic_id,text,source_url,speaker,party from int_segments order by chunk_id').df()
    import pandas as pd
    cached=pd.read_parquet(ROOT/'data/features/chunks.parquet')
    emb=np.load(ROOT/'data/features/embeddings.npy',mmap_mode='r')
    lookup={cid:i for i,cid in enumerate(cached.chunk_id)}
    examples=[]
    for tid, group in chunks.groupby('topic_id'):
        if tid<0:continue
        ix=[lookup[c] for c in group.chunk_id]
        vectors=np.asarray(emb[ix])
        center=vectors.mean(axis=0);center/=np.linalg.norm(center)
        order=np.argsort(vectors@center)[::-1]
        selected=set()
        for j in order:
            row=group.iloc[j]
            if row.speaker in selected:continue
            examples.append({'topic_id':int(tid),'text':row.text,'speaker':row.speaker,'party':row.party,'source_url':row.source_url})
            selected.add(row.speaker)
            if len(selected)==3:break
    payload['examples']=examples
    serial=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    (out/'analysis.json').write_text(serial,encoding='utf-8')
    template=(ROOT/'scripts/report.html').read_text(encoding='utf-8')
    html=template.replace('/*PLOTLY_LIBRARY*/',get_plotlyjs()).replace('/*ANALYSIS_DATA*/',serial)
    (out/'analys.html').write_text(html,encoding='utf-8')
    if args.inline_output:
        inline={}
        parties=['']+[r[0] for r in db.execute('select distinct party from stg_speeches where eligible order by party').fetchall()]
        for party in parties:
            predicate=' and party=?' if party else ''
            params=[party] if party else []
            total_words,speech_count=db.execute('select sum(word_count),count(*) from stg_speeches where eligible'+predicate,params).fetchone()
            topic_data=db.execute('select topic_label as label,sum(word_count) as words from int_segments where true'+predicate+' group by topic_label order by words desc',params).df()
            denom=topic_data.words.sum()
            topic_data['share']=100*topic_data.words/denom
            word_data=db.execute('select word,sum(occurrences) as occurrences from mart_word_usage where true'+predicate+' group by word order by occurrences desc limit 8',params).df()
            word_data['rate']=1000*word_data.occurrences/total_words
            mentions=db.execute("select target,sum(mentions) as mentions from mart_mentions where kind='person' and not self_mention"+predicate+' group by target order by mentions desc limit 8',params).df()
            inline[party]={'topics':topic_data.head(10)[['label','share']].to_dict('records'),'words':word_data[['word','rate']].to_dict('records'),'mentions':mentions.to_dict('records'),'speeches':speech_count}
        fragment=(ROOT/'scripts/inline.html').read_text(encoding='utf-8').replace('/*INLINE_DATA*/',json.dumps(inline,ensure_ascii=False).replace('</','<\\/'))
        Path(args.inline_output).write_text(fragment,encoding='utf-8')
    print(json.dumps({'report':str(out/'analys.html'),'topics':payload['topics'],'top_mentions':sorted(payload['mentions'],key=lambda x:x['mentions'],reverse=True)[:8]},ensure_ascii=False))


if __name__=='__main__':main()
