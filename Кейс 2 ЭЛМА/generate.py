# -*- coding: utf-8 -*-
import pandas as pd
from collections import Counter, defaultdict

path = r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 2 ЭЛМА\students.csv'
df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
df['EventIndex'] = df['EventIndex'].astype(int)
df = df.sort_values(['ProcessInstanceId','EventIndex'])

# ---- Variants ----
def route(g):
    return ' > '.join(g['ActivityName'].tolist())

rc = Counter()
for pid,g in df.groupby('ProcessInstanceId'):
    rc[route(g)] += 1

total = sum(rc.values())
rows = []
for i,(route_str, cnt) in enumerate(rc.most_common(), start=1):
    rows.append({'Variant': 'V%d' % i, 'Route': route_str, 'NumberOfCases': cnt, 'Share': round(cnt/total, 6)})
variants = pd.DataFrame(rows)
variants.to_csv(r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 2 ЭЛМА\variants.csv',
                index=False, encoding='utf-8-sig')

# ---- Transitions (directly-follows pairs of ActivityName, deduped) ----
pairs = set()
pair_count = Counter()
for pid,g in df.groupby('ProcessInstanceId'):
    names = g['ActivityName'].tolist()
    for a,b in zip(names, names[1:]):
        pairs.add((a,b))
        pair_count[(a,b)] += 1

# order logically
order = [
    ('Регистрация заявки','Первичная проверка'),
    ('Первичная проверка','Согласование руководителем'),
    ('Первичная проверка','Заявка отклонена'),
    ('Согласование руководителем','Проверка бюджета'),
    ('Согласование руководителем','Доработка заявки'),
    ('Согласование руководителем','Заявка отклонена'),
    ('Согласование руководителем','Заявка отменена'),
    ('Доработка заявки','Первичная проверка'),
    ('Проверка бюджета','Исполнение закупки'),
    ('Проверка бюджета','Дополнительное согласование'),
    ('Дополнительное согласование','Исполнение закупки'),
    ('Исполнение закупки','Заявка выполнена'),
]
# ensure no missing/extra
assert set(order) == pairs, (set(order)^pairs)

tr = pd.DataFrame(order, columns=['SourceActivity','TargetActivity'])
tr.to_csv(r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 2 ЭЛМА\student_transitions.csv',
          index=False, encoding='utf-8-sig')

out=[]
out.append('VARIANTS (sum=%d):' % total)
for i,(route_str,cnt) in enumerate(rc.most_common(),1):
    out.append('V%d  n=%d  share=%.3f' % (i, cnt, cnt/total))
out.append('')
out.append('TRANSITIONS (pair -> count):')
for a,b in order:
    out.append('  %s -> %s : %d' % (a,b,pair_count[(a,b)]))
out.append('')
out.append('total adjacent pairs = %d (events - processes = 6508-1000)' % sum(pair_count.values()))

with open(r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 2 ЭЛМА\summary.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done: variants=%d, transitions=%d' % (len(variants), len(tr)))
