import csv
import io
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from unittest.mock import patch

import pytest

from app.community.parser import BRASILIA
from app.community.importer import PreviewStore
from app.community.routes import PrivateAccessFilter
from app.db import connect,initialize


def export_text(messages, days_ago=1, iphone=False):
    base = datetime.now(BRASILIA).replace(hour=9,minute=0,second=0,microsecond=0)-timedelta(days=days_ago)
    lines=[]
    for i,(author,text) in enumerate(messages):
        stamp=base+timedelta(minutes=i)
        prefix=f"[{stamp:%d/%m/%Y, %H:%M:%S}] " if iphone else f"{stamp:%d/%m/%Y, %H:%M} - "
        lines.append(prefix+(author+": " if author else "")+text)
    return "\n".join(lines).encode()


def preview(admin,group,messages=None,raw=None,**params):
    return admin.post('/api/conversations/preview',params={"group_id":group['id'],**params},content=raw if raw is not None else export_text(messages),headers={"Content-Type":"text/plain"})


def import_messages(admin,group,messages=None,raw=None):
    result=preview(admin,group,messages,raw)
    assert result.status_code == 200,result.text
    response=admin.post('/api/conversations/import',json={"token":result.json()['token'],"confirmed":True})
    assert response.status_code == 201,response.text
    return response.json()


@pytest.mark.parametrize('path',['/api/conversations/policy','/api/conversations/messages','/api/conversations/imports','/api/conversations/topics','/api/intelligence','/api/intelligence/report'])
def test_community_requires_authentication(client,path):
    assert client.get(path).status_code == 401


def test_preview_before_persistence_no_original_names_or_phones(admin,group):
    raw=export_text([('Pessoa Fictícia A','Fale com Pessoa Fictícia B por exemplo@example.com.'),('Pessoa Fictícia B','Meu telefone fictício é +55 (11) 00000-0000.')],iphone=True)
    result=preview(admin,group,raw=raw)
    assert result.status_code == 200,result.text
    payload=result.json()
    assert payload['summary']['ready'] == 2
    assert admin.get('/api/conversations/messages').json()['total'] == 0
    assert 'Fictícia A' not in result.text and 'Fictícia B' not in result.text
    assert 'exemplo@example.com' not in result.text and '00000-0000' not in result.text
    assert 'repeat_token' not in result.text and 'url_analysis' not in result.text
    first=admin.post('/api/conversations/import',json={'token':payload['token'],'confirmed':True})
    assert first.status_code == 201
    rows=admin.get('/api/conversations/messages').json()['items']
    assert all(row['participant'].startswith('Pessoa-') for row in rows)
    assert 'fingerprint' not in str(rows)
    with connect(admin.settings.database_path) as conn:
        stored=' '.join(str(tuple(row)) for row in conn.execute('SELECT * FROM conversation_messages'))
    assert 'exemplo@example.com' not in stored and '00000-0000' not in stored
    assert 'Fictícia A' not in stored and 'Fictícia B' not in stored


def test_duplicate_overlap_and_groups(admin,group):
    raw=export_text([('Autor Fictício','Como sacar na HUB?'),('Outro Fictício','Mensagem de apoio')])
    assert import_messages(admin,group,raw=raw)['inserted'] == 2
    p=preview(admin,group,raw=raw).json()
    assert p['summary']['duplicates'] == 2 and p['summary']['ready'] == 0
    same=admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':True}).json()
    assert same['inserted'] == 0
    extended=raw+b'\n'+export_text([('Autor Fictício','Nova mensagem')]).replace(b'09:00',b'10:00')
    assert import_messages(admin,group,raw=extended)['inserted'] == 1
    other=admin.post('/api/groups',json={'name':'Outro fictício'}).json()
    assert import_messages(admin,other,raw=raw)['inserted'] == 2
    assert admin.get('/api/conversations/messages').json()['total'] == 5


def test_concurrent_confirmations_do_not_duplicate(admin,group):
    raw=export_text([('Autor Fictício','Conteúdo de teste')])
    tokens=[preview(admin,group,raw=raw).json()['token'] for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses=list(executor.map(lambda token:admin.post('/api/conversations/import',json={'token':token,'confirmed':True}),tokens))
    assert all(r.status_code == 201 for r in responses)
    assert sum(r.json()['inserted'] for r in responses) == 1


def test_policy_is_explicit_and_independent(admin,group):
    assert admin.get('/api/conversations/policy').json()['retention_days'] == 7
    assert admin.get('/api/rules').json()['retention_days'] == 7
    raw=export_text([('Autor Fictício','Conversa de vinte dias')],days_ago=20)
    first=preview(admin,group,raw=raw).json()
    assert first['summary']['expired'] == 1 and first['summary']['ready'] == 0
    assert admin.put('/api/conversations/policy',json={'retention_days':30}).status_code == 200
    assert admin.get('/api/rules').json()['retention_days'] == 7
    assert import_messages(admin,group,raw=raw)['inserted'] == 1
    assert admin.put('/api/conversations/policy',json={'retention_days':7}).status_code == 409
    result=admin.put('/api/conversations/policy',json={'retention_days':7,'confirm_deletion':True})
    assert result.json()['deleted'] == 1
    assert admin.get('/api/conversations/messages').json()['total'] == 0


def test_preview_invalidation_after_policy_rules_logout_and_discard(admin,group):
    p=preview(admin,group,[('Autor Fictício','Teste')]).json()
    admin.put('/api/conversations/policy',json={'retention_days':30})
    assert admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':True}).status_code == 409
    p=preview(admin,group,[('Autor Fictício','Teste')]).json()
    rules=admin.get('/api/rules').json();rules['casino_domains'].append('novo-ficticio.example')
    admin.put('/api/rules',json=rules)
    assert admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':True}).status_code == 409
    p=preview(admin,group,[('Autor Fictício','Teste')]).json()
    assert admin.delete('/api/conversations/preview/'+p['token']).status_code == 200
    assert admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':True}).status_code == 404
    p=preview(admin,group,[('Autor Fictício','Teste')]).json()
    admin.post('/api/auth/logout')
    admin.headers['X-CSRF-Token']=admin.get('/api/auth/session').json()['csrf']
    login=admin.post('/api/auth/login',json={'username':'admin_teste','password':'senha-ficticia-12345'}).json()
    admin.headers['X-CSRF-Token']=login['csrf']
    assert admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':True}).status_code == 404


def test_preview_memory_expiry_and_owner():
    store=PreviewStore()
    with patch('app.community.importer.time.time',return_value=100):
        token=store.put('sessao-a',{'messages':[]})
        assert store.get('sessao-b',token) is None
    with patch('app.community.importer.time.time',return_value=701):
        assert store.get('sessao-a',token) is None


def test_preview_cleanup_removes_expired_data_without_a_read():
    store=PreviewStore()
    with patch('app.community.importer.time.time',return_value=100):
        store.put('sessao-a',{'messages':['apenas exemplo fictício']})
    with patch('app.community.importer.time.time',return_value=701):
        store.cleanup()
    assert store.items=={}


def test_moderation_reused_without_notifications_and_simulator_unchanged(admin,group):
    before=admin.get('/api/dashboard').json()['stats']
    with patch('app.services.notifications.LocalNotificationSink.emit',side_effect=AssertionError('não notificar histórico')):
        import_messages(admin,group,[('Autor Fictício','https://cassino-demo.example/bonus'),('Outro Fictício','https://shopee.com.br/produto')])
    after=admin.get('/api/dashboard').json()['stats']
    assert before == after
    rows=admin.get('/api/conversations/messages').json()['items']
    assert {r['status'] for r in rows} == {'suspeita','critica'}
    assert all(not r['analysis']['urls'] for r in rows)
    assert all('histórico' in r['analysis']['recommendation'] for r in rows)


def test_numeric_own_referral_classified_before_redaction(admin,group):
    admin.post('/api/affiliates',json={'platform':'Teste','domain':'teste.example','referral_url':'https://teste.example/?ref=123456789','affiliate_code':'123456789','affiliate_parameters':['ref']})
    import_messages(admin,group,[('Autor Fictício','https://teste.example/?ref=123456789')])
    row=admin.get('/api/conversations/messages').json()['items'][0]
    assert row['status'] == 'permitida'
    assert '123456789' not in row['content']


def test_duplicate_text_and_burst_windows_use_historical_time(admin,group):
    raw=export_text([('Autor Fictício','Mesmo texto')]*3).replace(b'09:02',b'09:01')
    # A terceira mensagem tem outro instante, mantendo a mesma janela de 120s.
    raw=raw.rsplit(b'09:01',1)[0]+b'09:01:30'+raw.rsplit(b'09:01',1)[1]
    import_messages(admin,group,raw=raw)
    rows=admin.get('/api/conversations/messages').json()['items']
    assert any(f['rule']=='repeat' for r in rows for f in r['analysis'].get('findings',[]))


def test_intelligence_questions_answers_platforms_and_filters(admin,group):
    import_messages(admin,group,[('Fictício A','Como faço para sacar na HUB?'),('Fictício B','Alguém conseguiu retirar dinheiro da HUB?'),('Fictício C','Como funciona o saque da HUB?'),('Fictício D','Para sacar na HUB, acesse a área de pagamentos.'),('Fictício A','O cadastro no Mimix está com erro.'),('Fictício B','Como abrir um ticket no Flambra?')])
    result=admin.get('/api/intelligence').json()
    assert result['totals']['analyzed'] == 6
    assert result['totals']['questions'] == 4
    assert result['totals']['unanswered'] == 1
    topic=next(t for t in result['topics'] if t['label']=='Saque na HUB')
    assert topic['questions'] == 3 and topic['count'] == 4
    assert next(p for p in result['platforms'] if p['label']=='Mimix')['complaints'] == 1
    assert sum(row['count'] for row in result['hours']) == 6
    assert sum(row['count'] for row in result['weekdays']) == 6
    assert result['suggestions']
    assert admin.get('/api/intelligence?group_id=999').json()['totals']['messages'] == 0
    assert admin.get('/api/intelligence?since=2026-10-15&until=2026-10-01').status_code == 422


def test_topic_rename_move_merge_and_manual_answer_preserved(admin,group):
    raw=export_text([('Fictício A','Como sacar na HUB?'),('Fictício B','Como cadastrar no Mimix?')])
    import_messages(admin,group,raw=raw)
    topics=admin.get('/api/conversations/topics').json()
    source=next(t for t in topics if t['label']=='Saque na HUB')
    assert admin.put('/api/conversations/topics/'+source['key'],json={'label':'Saques — revisão fictícia','reviewed':True}).status_code == 200
    message=next(r for r in admin.get('/api/conversations/messages').json()['items'] if r['topic_key']==source['key'])
    assert admin.put(f"/api/conversations/messages/{message['id']}/correction",json={'new_topic_label':'Tutorial fictício de saque','answer_state':'answered'}).status_code == 200
    import_messages(admin,group,raw=raw)
    reviewed=admin.get(f"/api/conversations/messages/{message['id']}").json()
    assert reviewed['topic_label']=='Tutorial fictício de saque' and reviewed['answer_state']=='answered'
    assert admin.get('/api/intelligence').json()['totals']['unanswered'] == 1
    topics=admin.get('/api/conversations/topics').json()
    assert len(topics) == 2
    assert admin.post('/api/conversations/topics/merge',json={'source':topics[0]['key'],'target':topics[1]['key']}).status_code == 200
    assert len(admin.get('/api/conversations/topics').json()) == 1


def test_period_search_pagination_and_deletion_preserve_stage_one(admin,group):
    import_messages(admin,group,[('Fictício A','Mensagem alfa'),('Fictício B','Mensagem beta')])
    assert admin.get('/api/conversations/messages?q=alfa&page_size=1').json()['total']==1
    yesterday=(datetime.now(BRASILIA).date()-timedelta(days=1)).isoformat()
    assert admin.get('/api/conversations/messages',params={'since':yesterday,'until':yesterday,'group_id':group['id']}).json()['total']==2
    row=admin.get('/api/conversations/messages').json()['items'][0]
    assert admin.request('DELETE',f"/api/conversations/messages/{row['id']}",json={'confirmation':'EXCLUIR'}).json()['deleted']==1
    assert admin.request('DELETE','/api/conversations/messages',json={'confirmation':'errado'}).status_code==422
    assert admin.request('DELETE','/api/conversations/messages',json={'confirmation':'EXCLUIR','group_id':group['id']}).json()['deleted']==1
    assert admin.get('/api/conversations/imports').json()==[]
    assert len(admin.get('/api/groups').json())==1
    assert admin.get('/api/rules').json()['retention_days']==7


@pytest.mark.parametrize('format',['md','jsonl','csv'])
def test_reports_are_aggregate_only_and_period_is_explicit(admin,group,format):
    import_messages(admin,group,[('Fictício A','Como sacar na HUB? CONTEUDO_UNICO_FICTICIO')])
    response=admin.get('/api/intelligence/report',params={'format':format,'days':30})
    assert response.status_code==200
    assert 'attachment' in response.headers['content-disposition']
    assert 'CONTEUDO_UNICO_FICTICIO' not in response.text
    assert 'Pessoa-' not in response.text and 'Fictício A' not in response.text
    assert 'Saque na HUB' in response.text
    if format=='jsonl':
        records=[json.loads(line) for line in response.text.splitlines()]
        assert records[0]['requested_days']==30 and records[0]['retention_days']==7
    if format=='csv':
        assert list(csv.reader(io.StringIO(response.text)))


def test_import_errors_no_preview_without_confirmation_csrf_and_validation(admin,group):
    p=preview(admin,group,[('Fictício A','Texto')]).json()
    assert admin.post('/api/conversations/import',json={'token':p['token'],'confirmed':False}).status_code==422
    assert preview(admin,{'id':999},[('Fictício A','Texto')]).status_code==404
    assert preview(admin,group,raw=b'nada valido').status_code==422
    assert admin.get('/api/intelligence?days=90').status_code==422
    admin.headers.pop('X-CSRF-Token')
    assert preview(admin,group,[('Fictício A','Texto')]).status_code==403


def test_access_logs_drop_private_search_and_preview_tokens():
    filter=PrivateAccessFilter()
    record=logging.LogRecord('uvicorn.access',20,'',1,'%s - %s %s %s %s',('local','GET','/api/conversations/messages?q=PRIVADO','1.1',200),None)
    filter.filter(record)
    assert 'PRIVADO' not in record.getMessage()
    record.args=('local','DELETE','/api/conversations/preview/TOKEN_FICTICIO','1.1',200)
    filter.filter(record)
    assert 'TOKEN_FICTICIO' not in record.getMessage()


def test_schema_migration_is_idempotent_and_preserves_existing_records(admin,group):
    before=admin.get('/api/groups').json()
    initialize(admin.settings.database_path,False)
    initialize(admin.settings.database_path,False)
    assert admin.get('/api/groups').json()==before
    assert admin.get('/api/auth/session').json()['username']=='admin_teste'


def test_system_content_is_minimized_even_for_unknown_people(admin,group):
    import_messages(admin,group,[('', 'Pessoa Fictícia Sem Mensagens alterou a descrição do grupo: detalhe reservado')])
    row=admin.get('/api/conversations/messages').json()['items'][0]
    assert row['kind']=='system'
    assert 'Sem Mensagens' not in row['content'] and 'detalhe reservado' not in row['content']
    assert row['content']=='[Mensagem de sistema omitida por privacidade]'


def test_unicode_search_and_server_upload_limit(admin,group,monkeypatch):
    import_messages(admin,group,[('Fictício A','DÚVIDA sobre avaliação')])
    assert admin.get('/api/conversations/messages?q=duvida').json()['total']==1
    monkeypatch.setattr('app.community.routes.MAX_BYTES',10)
    assert preview(admin,group,raw=b'x'*11).status_code==413


def test_future_dates_and_expired_preview_confirmation(admin,group):
    raw=export_text([('Fictício A','Data futura')],days_ago=-2)
    result=preview(admin,group,raw=raw).json()
    assert result['summary']['future']==1 and result['summary']['ready']==0
    with connect(admin.settings.database_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM conversation_messages').fetchone()[0]==0


def test_reports_prevent_spreadsheet_formula_injection(admin,group):
    import_messages(admin,group,[('Fictício A','Como sacar na HUB?')])
    topic=admin.get('/api/conversations/topics').json()[0]
    admin.put('/api/conversations/topics/'+topic['key'],json={'label':'=HYPERLINK(ficticio)','reviewed':True})
    response=admin.get('/api/intelligence/report?format=csv')
    rows=list(csv.reader(io.StringIO(response.text)))
    labels=[row[1] for row in rows[1:]]
    assert "'=HYPERLINK(ficticio)" in labels
    assert '=HYPERLINK(ficticio)' not in labels


def test_reimport_earlier_messages_updates_frequency_without_false_duplicates(admin,group):
    raw=export_text([('Fictício A','Repetida')]*3)
    last=raw.splitlines()[-1]
    assert import_messages(admin,group,raw=last)['inserted']==1
    assert import_messages(admin,group,raw=raw)['inserted']==2
    rows=admin.get('/api/conversations/messages').json()['items']
    assert rows[0]['status']=='suspeita'
    assert any(f['rule']=='repeat' for f in rows[0]['analysis']['findings'])


def test_omitted_media_not_inferred_as_identical_or_a_filename_link(admin,group):
    import_messages(admin,group,[('Fictício A','<Mídia oculta>')]*3+[('Fictício B','IMG-20261014-WA0001.jpg (file attached)')])
    rows=admin.get('/api/conversations/messages').json()['items']
    assert all(row['status']=='permitida' and row['topic_key'] is None for row in rows)
    assert admin.get('/api/intelligence').json()['topics']==[]
