from datetime import datetime

import pytest

from app.community.parser import parse_export, BRASILIA, MAX_BYTES
from app.community.privacy import pseudonym, minimize, privacy_key
from app.community.text import describe
from app.config import ROOT


@pytest.mark.parametrize("fixture,count,media", [("android_ficticio.txt",10,1),("iphone_ficticio.txt",5,1)])
def test_android_iphone_multiline_system_media(fixture,count,media):
    result = parse_export((ROOT / "tests/fixtures" / fixture).read_bytes())
    assert len(result.records) == count
    assert result.records[0].kind == "system"
    assert sum(row.kind == "media" for row in result.records) == media
    assert "\n" in result.records[1].content
    assert result.records[1].author == "Pessoa Fictícia A"


@pytest.mark.parametrize("header,order,expected", [
    ("10/14/26, 2:05 PM - Teste: Olá", "mdy", (2026,10,14,14,5)),
    ("[10/14/26, 12:05:01 AM] Teste: Olá", "mdy", (2026,10,14,0,5)),
    ("14.10.2026, 09:15 - Teste: Olá", "dmy", (2026,10,14,9,15)),
    ("2026-10-14, 09:15 - Teste: Olá", "dmy", (2026,10,14,9,15)),
])
def test_dates_and_ampm(header,order,expected):
    row = parse_export(header.encode(),date_order=order).records[0]
    stamp = datetime.fromtimestamp(row.timestamp,BRASILIA)
    assert (stamp.year,stamp.month,stamp.day,stamp.hour,stamp.minute) == expected


def test_explicit_ambiguous_date_and_offset():
    raw = b"03/04/2026, 10:00 - Teste: Texto"
    dmy = parse_export(raw,"dmy",-180).records[0]
    mdy = parse_export(raw,"mdy",-180).records[0]
    assert dmy.timestamp != mdy.timestamp
    utc = parse_export(raw,"dmy",0).records[0]
    assert dmy.timestamp - utc.timestamp == 3*3600


@pytest.mark.parametrize("encoding", ["utf-8-sig","utf-16","cp1252"])
def test_supported_encodings(encoding):
    raw = "14/10/2026, 10:00 - Teste Fictício: Dúvida sobre avaliação".encode(encoding)
    result = parse_export(raw)
    assert "Dúvida" in result.records[0].content
    if encoding == "cp1252":
        assert result.warnings


def test_invalid_date_errors_never_include_text():
    raw = "cabeçalho solto\n31/02/2026, 10:00 - Nome Privado: CONTEUDO_NAO_DEVE_IR_AO_ERRO\ncontinuação\n14/10/2026, 10:01 - Teste: válido".encode()
    result = parse_export(raw)
    assert len(result.records) == 1
    assert result.total_errors == 1
    assert result.errors[0]["line"] == 2
    assert "CONTEUDO" not in str(result.errors)
    assert result.ignored_lines == 2


@pytest.mark.parametrize("raw", [b"",b"arquivo sem mensagens",b"PK\x00\x00zip",b"x"*(MAX_BYTES+1)], ids=["vazio","sem-mensagens","binario","maior-que-limite"])
def test_invalid_or_oversized_file(raw):
    with pytest.raises(ValueError):
        parse_export(raw)


def test_oversized_message_does_not_join_next_message():
    raw = ("14/10/2026, 10:00 - Teste: "+"x"*10001+"\n14/10/2026, 10:01 - Teste: válida").encode()
    result = parse_export(raw)
    assert result.total_errors == 1
    assert len(result.records) == 1
    assert result.records[0].content == "válida"


def test_pseudonyms_stable_and_keyed(tmp_path):
    key = privacy_key(str(tmp_path/'demo.sqlite3'))
    assert key == privacy_key(str(tmp_path/'demo.sqlite3'))
    assert pseudonym(key," Pessoa Fictícia A ") == pseudonym(key,"pessoa fictícia a")
    assert pseudonym(key,"+55 (11) 00000-0000") == pseudonym(key,"+5511000000000")
    assert pseudonym(key,"Pessoa Fictícia A") != pseudonym(b'outra-chave',"Pessoa Fictícia A")
    assert "Fictícia" not in pseudonym(key,"Pessoa Fictícia A")


def test_personal_data_and_known_mentions_minimized():
    text = "Pessoa Fictícia A, envie para exemplo@example.com ou +55 (11) 00000-0000. Documento 000.000.000-00. https://site.example/?access_token=SEGREDO_FICTICIO"
    result = minimize(text,{"Pessoa Fictícia A":"Pessoa-abcdef123456"})
    for private in ("Fictícia A","exemplo@example.com","00000-0000","000.000.000-00","SEGREDO_FICTICIO"):
        assert private not in result
    assert "Pessoa-abcdef123456" in result


def test_withdrawal_synonyms_share_topic():
    texts = ["Como faço para sacar na HUB?","Alguém conseguiu retirar dinheiro da HUB?","Como funciona o saque da HUB?"]
    descriptions = [describe(text) for text in texts]
    assert len({d["key"] for d in descriptions}) == 1
    assert descriptions[0]["label"] == "Saque na HUB"
    assert all(d["question"] for d in descriptions)
    assert describe("Como sacar no Mimix?")["key"] != descriptions[0]["key"]


def test_complaints_platforms_and_questions():
    result = describe("Não consigo cadastrar no Mimix. O cadastro está com erro.")
    assert result["complaint"]
    assert result["platforms"] == ["Mimix"]
    assert result["label"] == "Cadastro na Mimix"
    assert not result["question"]


def test_system_message_with_colon_is_not_a_participant():
    row=parse_export('14/10/2026, 09:00 - Você alterou a descrição do grupo: texto fictício'.encode()).records[0]
    assert row.kind == 'system'
    assert row.author == ''
