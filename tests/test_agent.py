import json
from tests.test_platform import clients, create_project
from server.automation import drain_jobs


def review_model(calls, review=None, reflect=None):
    def model(purpose, payload):
        calls.append((purpose, payload))
        if purpose == 'project_chunk': return {'summary': '方案V3已提交待汇报。', 'risks': []}
        if purpose == 'project_review':
            return review(payload) if review else {
                'thinking': {'facts': ['我方提交方案V3'], 'changes': '首次评估', 'stage_reasoning': '方案已出V3，尚未汇报', 'gaps': ['汇报时间']},
                'stage': 'proposal', 'stage_progress': 60,
                'nodes': [{'key': 'negotiation', 'status': 'done', 'evidence': '已多轮沟通'}, {'key': 'requirements', 'status': 'done', 'evidence': '客户回传需求确认'},
                          {'key': 'contract', 'status': 'done', 'evidence': ''}],
                'summary': '为甲方建设运营平台，方案V3已提交。', 'next': '预约汇报。',
                'actions': [{'title': '预约客户汇报时间', 'why': '方案已就绪', 'priority': 'high', 'node': 'proposal'}, {'title': '整理报价清单', 'why': '汇报需要', 'priority': 'low'}],
                'questions': ['汇报对象是谁'], 'points': ['方案V3已交，汇报没约', '']}
        if purpose == 'project_reflect': return reflect(payload) if reflect else {'issues': []}
        if purpose == 'timeline_digest': return {'items': [{'key': e['key'], 'headline': '提交方案V3', 'points': ['新增汇报版目录。', '', '报价待补'] } for e in payload['entries']]}
        if purpose == 'project_ask':
            return {'thinking': ['理解问题', '查找方案进展'], 'answer': '**建议**先预约汇报。', 'basis': ['方案.md'], 'follow_ups': ['报价多少']}
        return {'summary': '方案说明。', 'previous': '无', 'current': '收到方案', 'next': '汇报'}
    return model


def analyse(a, p):
    a.post('/api/projects/' + p['id'] + '/analyze', json={})
    drain_jobs(a.app, limit=5)
    return a.get('/api/projects/' + p['id'] + '/workflow').json()


def test_agent_reasons_before_judging_and_progress_is_weighted(clients):
    a, _ = clients
    p = create_project(a)
    a.post('/api/projects/' + p['id'] + '/files', files={'file': ('方案V3.md', '方案V3已提交待汇报。'.encode(), 'text/markdown')})
    calls = []
    a.app.state.analysis_model = review_model(calls)
    flow = analyse(a, p)
    insight = flow['analysis']['insight']
    assert insight['thinking']['stage_reasoning'] == '方案已出V3，尚未汇报'
    assert insight['points'] == ['方案V3已交，汇报没约']
    nodes = {n['key']: n['status'] for n in insight['nodes']}
    # A "done" claim without evidence is downgraded; the stage is the first unfinished node.
    assert nodes['contract'] == 'doing' and nodes['requirements'] == 'done'
    assert insight['stage'] == 'proposal' and insight['stage_progress'] == 60
    # 5 + 10 done, proposal 13 x 60%, contract started (half of 10)
    assert flow['progress']['percent'] == round(5 + 10 + 13 * 0.6 + 5) and flow['progress']['basis'] == 'ai'
    assert flow['progress']['confirmed_percent'] == 0
    assert [a_['title'] for a_ in insight['actions']] == ['预约客户汇报时间', '整理报价清单']
    purposes = [c[0] for c in calls]
    assert purposes.index('project_review') < purposes.index('project_reflect')
    review = next(c[1] for c in calls if c[0] == 'project_review')
    assert review['previous_insight'] is None and 'signal_hash' not in review
    entry = next(i for i in a.get('/api/projects/' + p['id'] + '/activity').json()['items'] if i['kind'] == 'file')
    assert entry['summary'] == '提交方案V3' and entry['points'] == ['新增汇报版目录', '报价待补']


def test_reflection_corrects_and_human_confirmation_is_the_floor(clients):
    a, _ = clients
    p = create_project(a)
    url = '/api/projects/' + p['id'] + '/workflow'
    for key in ('negotiation', 'requirements', 'proposal', 'contract'):
        a.put(url + '/' + key, json={'version': 0, 'confirmed': True, 'occurred_at': '2026-10-12T09:00:00+08:00', 'evidence': '已确认'})
    a.post('/api/projects/' + p['id'] + '/files', files={'file': ('计划.md', '开发计划。'.encode(), 'text/markdown')})
    calls = []
    a.app.state.analysis_model = review_model(calls, reflect=lambda payload: {'issues': ['开发仅有计划'], 'stage': 'development', 'stage_progress': 10, 'remove_actions': ['整理报价清单']})
    flow = analyse(a, p)
    insight = flow['analysis']['insight']
    assert insight['stage'] == 'development' and insight['stage_progress'] == 10
    assert insight['thinking']['review'] == ['开发仅有计划']
    assert [x['title'] for x in insight['actions']] == ['预约客户汇报时间']
    assert flow['progress']['percent'] == 38 + round(32 * 0.1)
    assert all(n['status'] == 'done' for n in insight['nodes'][:4])


def test_feedback_creates_tasks_and_is_remembered(clients):
    a, _ = clients
    p = create_project(a)
    base = '/api/projects/' + p['id']
    a.post(base + '/files', files={'file': ('方案.md', '方案。'.encode(), 'text/markdown')})
    calls = []
    a.app.state.analysis_model = review_model(calls)
    actions = analyse(a, p)['analysis']['insight']['actions']
    r = a.post(base + '/insight/actions', json={'action_id': actions[0]['id'], 'verdict': 'adopt'})
    assert r.status_code == 200 and r.json()['task_id']
    assert a.post(base + '/insight/actions', json={'action_id': actions[0]['id'], 'verdict': 'dismiss'}).status_code == 409
    assert a.post(base + '/insight/actions', json={'action_id': actions[1]['id'], 'verdict': 'dismiss', 'note': '报价已发'}).status_code == 200
    assert any(t['title'] == '预约客户汇报时间' for t in a.get(base).json()['tasks'])
    states = {x['title']: x['state'] for x in a.get(base + '/workflow').json()['analysis']['insight']['actions']}
    assert states == {'预约客户汇报时间': 'adopt', '整理报价清单': 'dismiss'}
    calls.clear()
    insight = analyse(a, p)['analysis']['insight']
    review = next(c[1] for c in calls if c[0] == 'project_review')
    assert {f['title'] for f in review['manager_feedback']} == {'预约客户汇报时间', '整理报价清单'}
    assert review['previous_insight']['stage'] == 'proposal'
    # Suggestions the manager already handled are never proposed again.
    assert insight['actions'] == []


def test_ask_agent_answers_with_reasoning_and_history(clients):
    a, b = clients
    p = create_project(a)
    base = '/api/projects/' + p['id']
    calls = []
    a.app.state.analysis_model = review_model(calls)
    r = a.post(base + '/ask', json={'question': '下一步先做什么？'})
    assert r.status_code == 201, r.text
    assert r.json()['thinking'] == ['理解问题', '查找方案进展'] and r.json()['follow_ups'] == ['报价多少']
    payload = next(c[1] for c in calls if c[0] == 'project_ask')
    assert payload['question'] == '下一步先做什么？' and 'progress' in payload
    assert a.get(base + '/asks').json()[0]['answer'].startswith('**建议**')
    assert b.get(base + '/asks').status_code in (401, 404)


def test_delete_recording_removes_derived_records(clients):
    a, _ = clients
    p = create_project(a)
    m = a.post('/api/projects/' + p['id'] + '/meetings', json={'title': '需求沟通'}).json()
    a.patch('/api/meetings/' + m['id'], json={'version': m['version'], 'transcript': '客户确认需求'})
    from server.db import Meeting
    with a.app.state.sessions() as db:
        db.get(Meeting, m['id']).status = 'recording'; db.commit()
    assert a.delete('/api/meetings/' + m['id']).status_code == 409
    with a.app.state.sessions() as db:
        db.get(Meeting, m['id']).status = 'finished'; db.commit()
    assert a.delete('/api/meetings/' + m['id']).status_code == 204
    assert a.get('/api/meetings/' + m['id']).status_code == 404
    assert all(x['id'] != m['id'] for x in a.get('/api/meetings').json())
    assert not any(i['kind'] == 'meeting' for i in a.get('/api/projects/' + p['id'] + '/activity').json()['items'])


def test_file_name_date_is_business_time():
    from types import SimpleNamespace
    from server.recording_imports import business_time
    f = SimpleNamespace(name='[codes] source · 甲方资料 · 会议纪要-20261013-一期.md', source_modified_at='2026-10-15T01:00:00+00:00', created_at='', source_time_basis='file_modified')
    assert business_time(f) == ('2026-10-13', 'filename')
    folder = SimpleNamespace(name='[codes] 产品介绍-20261009 · 产品介绍.pdf', source_modified_at='2026-10-15T01:00:00+00:00', created_at='', source_time_basis='file_modified')
    assert business_time(folder) == ('2026-10-09', 'filename')
    plain = SimpleNamespace(name='[codes] 方案.md', source_modified_at='2026-10-15T01:00:00+00:00', created_at='', source_time_basis='file_modified')
    assert business_time(plain) == ('2026-10-15T01:00:00+00:00', 'file_modified')


def test_ask_streams_markdown_and_stores_follow_ups(clients):
    a, b = clients
    p = create_project(a)
    base = '/api/projects/' + p['id']
    seen = []
    def streamer(purpose, payload):
        seen.append((purpose, payload['question']))
        yield from ['**先约汇报**', '\n- 方案V3已就绪\n', '<<<追问>>>\n报价多少\n- 谁拍板\n']
    a.app.state.analysis_stream = streamer
    r = a.post(base + '/ask/stream', json={'question': '下一步？'})
    assert r.status_code == 200 and r.headers['content-type'].startswith('text/event-stream')
    events = [blk.split('\n') for blk in r.text.strip().split('\n\n')]
    kinds = [e[0].removeprefix('event: ') for e in events]
    assert kinds == ['delta', 'delta', 'delta', 'done']
    done = json.loads(events[-1][1].removeprefix('data: '))
    assert done['answer'] == '**先约汇报**\n- 方案V3已就绪' and done['follow_ups'] == ['报价多少', '谁拍板']
    assert seen == [('project_ask', '下一步？')]
    assert a.get(base + '/asks').json()[0]['id'] == done['id']
    assert b.post(base + '/ask/stream', json={'question': 'x'}).status_code in (401, 404)


def test_ask_stream_reports_model_failure(clients):
    a, _ = clients
    p = create_project(a)
    from server.analysis_model import AnalysisError
    def broken(purpose, payload):
        yield '半句'
        raise AnalysisError('AI回答中断，请重试')
    a.app.state.analysis_stream = broken
    r = a.post('/api/projects/' + p['id'] + '/ask/stream', json={'question': '进度？'})
    assert r.text.rstrip().endswith('"message": "AI回答中断，请重试"}')
    assert a.get('/api/projects/' + p['id'] + '/asks').json() == []
