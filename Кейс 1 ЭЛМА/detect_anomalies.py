# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from collections import defaultdict

path = r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 1 ЭЛМА\students.csv'
df = pd.read_csv(path, encoding='utf-8-sig', dtype=str, keep_default_na=False)
df['EventIndex'] = df['EventIndex'].astype(int)
df['ts'] = pd.to_datetime(df['Timestamp'], utc=True)
df = df.sort_values(['ProcessInstanceId','EventIndex'])

AM = {
 'Регистрация заявки':'REG','Проверка заявки':'CHECK','Согласование руководителем':'MGR',
 'Согласование бюджета':'BUDGET','Проверка договора':'LEGAL','Исполнение заявки':'EXEC',
 'Доработка заявки':'REWORK','Завершение':'END','Внеплановая проверка':'AUDIT',
}

# task durations by TaskId
created = df[df['EventType']=='task_created'][['TaskId','ts']].rename(columns={'ts':'ts_c'})
completed = df[df['EventType']=='task_completed'][['TaskId','ts']].rename(columns={'ts':'ts_d'})
mdur = completed.merge(created, on='TaskId', how='inner')
mdur['dur_h'] = (mdur['ts_d'] - mdur['ts_c']).dt.total_seconds()/3600.0
dur_by_task = dict(zip(mdur['TaskId'], mdur['dur_h']))

rows = []
def add(pid, t, e):
    rows.append((pid, t, e))

for pid, g in df.groupby('ProcessInstanceId'):
    rt = g['RequestType'].iloc[0]
    amount = g['Amount'].iloc[0]
    ev = g[g['EventType']=='task_completed'].copy()
    ev['stage'] = ev['ActivityName'].map(AM)
    stages = ev['stage'].tolist()
    roles = ev['Role'].tolist()
    results = ev['Result'].tolist()
    tasks = ev['TaskId'].tolist()
    names_ru = ev['ActivityName'].tolist()
    route_ru = ' → '.join(names_ru)

    endres = g[g['EventType']=='process_completed']['Result'].iloc[0] if (g['EventType']=='process_completed').any() else None

    # 1. Self decision at manager step (role requester)
    for i,(s,r) in enumerate(zip(stages, roles)):
        if s=='MGR' and r=='requester':
            verb = 'согласовал' if results[i]=='accept' else 'отклонил'
            add(pid, 'Самосогласование',
                f'Этап «Согласование руководителем» выполнил сам заявитель (Role=requester, а не manager): '
                f'заявитель {verb} собственную заявку (result={results[i]}, тип {rt}, сумма {amount}). '
                f'Нарушение разделения обязанностей.')

    # 2. Missing manager step (fulfilled without MGR)
    if endres=='fulfilled' and 'MGR' not in stages:
        add(pid, 'Пропуск этапа руководителя',
            f'Заявка исполнена (fulfilled) без обязательного этапа «Согласование руководителем»: '
            f'маршрут {route_ru}. Тип {rt}, сумма {amount}.')

    # 3. Execution before approvals
    if 'EXEC' in stages:
        iexec = stages.index('EXEC')
        ibud = stages.index('BUDGET') if 'BUDGET' in stages else None
        ileg = stages.index('LEGAL') if 'LEGAL' in stages else None
        if ibud is not None and iexec < ibud:
            what = 'согласования бюджета'
            if ileg is not None and iexec < ileg:
                what = 'согласования бюджета и юридической проверки'
            add(pid, 'Исполнение до согласования',
                f'«Исполнение заявки» выполнено раньше {what}: маршрут {route_ru}. '
                f'Закупка начата до одобрения бюджетом{" и юристом" if ileg is not None else ""}.')

    # 4. Duplicate consecutive check
    for i in range(len(stages)-1):
        if stages[i]=='CHECK' and stages[i+1]=='CHECK':
            add(pid, 'Дубль проверки',
                f'Два подряд этапа «Проверка заявки» без возврата на доработку между ними: маршрут {route_ru}. '
                f'Повторная проверка не объяснена возвратом.')

    # 5. Excessive returns
    nret = results.count('return')
    if nret >= 3:
        add(pid, 'Многократный возврат',
            f'{nret} возвратов на доработку (типично 0–1): руководитель {nret} раз отправлял заявку на исправление, '
            f'маршрут {route_ru}.')

    # 6. Auditor
    if 'AUDIT' in stages:
        n_aud = stages.count('AUDIT')
        add(pid, 'Внеплановая проверка',
            f'В маршруте присутствует внеплановая проверка аудитором ({n_aud} задачи «Внеплановая проверка»): '
            f'{route_ru}. Допустимый, но необычный случай — требуется ручная проверка/обоснование.')

    # 7. Stuck check
    for s, t in zip(stages, tasks):
        if s=='CHECK' and t in dur_by_task and dur_by_task[t] >= 150:
            add(pid, 'Аномально долгая проверка',
                f'Этап «Проверка заявки» длился {dur_by_task[t]:.0f} ч '
                f'(медиана по всем заявкам ≈0.36 ч, 99-й перцентиль ≈70 ч).')

# Dedup
seen = set(); uniq = []
for pid, t, e in rows:
    key = (pid, t, e)
    if key not in seen:
        seen.add(key); uniq.append((pid, t, e))

# sort by type then pid for readability
type_order = ['Самосогласование','Пропуск этапа руководителя','Исполнение до согласования',
              'Дубль проверки','Многократный возврат','Внеплановая проверка','Аномально долгая проверка']
res = pd.DataFrame(uniq, columns=['ProcessInstanceId','AnomalyType','Explanation'])
res['_o'] = res['AnomalyType'].map({t:i for i,t in enumerate(type_order)})
res = res.sort_values(['_o','ProcessInstanceId']).drop(columns='_o')
res.to_csv(r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 1 ЭЛМА\anomalies.csv',
           index=False, encoding='utf-8-sig')

out=[]
out.append('ROWS=%d PIDs=%d' % (len(res), res['ProcessInstanceId'].nunique()))
out.append('')
for t,grp in res.groupby('AnomalyType'):
    out.append('%s: %d rows / %d pids' % (t, len(grp), grp['ProcessInstanceId'].nunique()))
with open(r'C:\Users\Пользователь\Desktop\Производственная практика 1  2026\кейс 1 ЭЛМА\anomaly_summary.txt','w',encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done rows=%d pids=%d' % (len(res), res['ProcessInstanceId'].nunique()))
