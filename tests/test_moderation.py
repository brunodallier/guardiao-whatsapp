import pytest

from app.moderation.engine import analyze
from app.moderation.urls import canonical_url, normalize_domain


@pytest.mark.parametrize("content", ["Falar de cassino é permitido.", "Alguém viu BET ontem?", "Minha compra da Shopee chegou.", "Como funciona o HUB e o Mimix?", "Mande um email para exemplo@empresa.com"])
def test_normal_conversations(content, rules):
    assert analyze(content, rules, [], [], 1000).status == "permitida"


@pytest.mark.parametrize("url", ["https://cassino-demo.example", "cassino-demo.example/bonus", "HTTPS://CASSINO-DEMO.EXAMPLE/x", "https://sub.cassino-demo.example/", "https://cassino-demo.example./", "www.cassino-demo.example"])
def test_confirmed_casino(url, rules):
    result = analyze("Confira " + url, rules, [], [], 1000)
    assert result.status == "critica"
    assert result.findings[0]["rule"] == "casino"
    assert "SIMULAÇÃO" in result.recommendation


@pytest.mark.parametrize("url", ["https://cassino-demo.example.evil.example", "https://naocassino-demo.example", "https://evil.example/?url=cassino-demo.example"])
def test_domain_boundary(url, rules):
    result = analyze(url, rules, [], [], 1000)
    assert result.status == "suspeita"
    assert not any(item["rule"] == "casino" for item in result.findings)


def test_allowlist_cannot_override_casino(rules):
    rules["allowed_domains"] = ["cassino-demo.example"]
    assert analyze("https://cassino-demo.example", rules, [], [], 1000).status == "critica"


@pytest.mark.parametrize("url", ["https://plataforma.example/?ref=MEU-DEMO", "https://plataforma.example/?ref=MEU%2DDEMO&utm_source=teste", "https://plataforma.example/convite/MEU-DEMO", "https://plataforma.example/ajuda"])
def test_own_links_and_plain_platform(url, rules, profile):
    assert analyze(url, rules, [profile], [], 1000).status == "permitida"


@pytest.mark.parametrize("url", ["https://plataforma.example/?ref=OUTRO", "https://plataforma.example/?ref=MEU-DEMO&ref=OUTRO", "https://plataforma.example/?ref=", "https://plataforma.example/?REF=OUTRO", "https://plataforma.example/convite/OUTRO", "https://plataforma.example/?ref=MEU-DEMO&aff_id=OUTRO"])
def test_foreign_affiliate(url, rules, profile):
    result = analyze(url, rules, [profile], [], 1000)
    assert result.status == "suspeita"
    assert result.findings[0]["rule"] == "affiliate"


def test_no_own_code_does_not_invent_identity(rules, profile):
    profile.update(referral_url="", affiliate_code="", affiliate_path_prefix="")
    assert analyze("https://plataforma.example/?ref=QUALQUER", rules, [profile], [], 1000).status == "suspeita"


def test_authorized_domain_keeps_foreign_affiliate_suspect(rules, profile):
    rules["allowed_domains"] = ["plataforma.example"]
    assert analyze("https://plataforma.example/?ref=OUTRO", rules, [profile], [], 1000).status == "suspeita"


@pytest.mark.parametrize("url,rule", [("https://shopee.com.br/p", "marketplace"), ("https://aliexpress.com/p", "marketplace"), ("https://shop.tiktok.com/p", "marketplace"), ("https://bit.ly/p", "unknown_link"), ("https://s.shopee.com.br/p", "unknown_link"), ("https://novidade.example/p", "unknown_link"), ("https://user:password@novidade.example/p", "unknown_link")])
def test_commercial_unknown_and_shortened(url, rule, rules):
    result = analyze(url, rules, [], [], 1000)
    assert result.status == "suspeita"
    assert result.findings[0]["rule"] == rule


def test_exact_authorization(rules):
    rules["allowed_links"] = ["https://docs.example/ajuda?a=1&b=2"]
    assert analyze("https://docs.example/ajuda?b=2&a=1", rules, [], [], 1000).status == "permitida"
    assert analyze("https://docs.example/outro", rules, [], [], 1000).status == "suspeita"


def test_authorized_shortener_remains_suspect(rules):
    rules["allowed_domains"] = ["bit.ly"]
    assert analyze("https://bit.ly/p", rules, [], [], 1000).status == "suspeita"


def test_repetition_threshold_and_window(rules):
    previous = [{"content": "Olá pessoal", "created_at": 990, "link_count": 0}]*2
    assert analyze("  OLÁ   pessoal ", rules, [], previous, 1000).findings[0]["rule"] == "repeat"
    assert analyze("Olá pessoal", rules, [], previous[:1], 1000).status == "permitida"
    assert analyze("Olá pessoal", rules, [], previous, 2000).status == "permitida"


def test_frequency(rules):
    previous = [{"content": f"Mensagem {i}", "created_at": 995, "link_count": 0} for i in range(5)]
    result = analyze("Mensagem nova", rules, [], previous, 1000)
    assert any(item["rule"] == "burst" for item in result.findings)
    assert analyze("Mensagem nova", rules, [], previous, 1020).status == "permitida"


def test_many_links(rules):
    rules["allowed_domains"] = ["docs.example"]
    previous = [{"content": "Links", "created_at": 995, "link_count": 4}]
    result = analyze("https://docs.example/ajuda", rules, [], previous, 1000)
    assert result.findings[0]["rule"] == "link_burst"


def test_rule_switches(rules):
    rules["enabled"] = dict.fromkeys(rules["enabled"], False)
    result = analyze("https://cassino-demo.example https://bit.ly/p", rules, [], [], 1000)
    assert result.status == "permitida"


def test_critical_priority_and_multiple_findings(rules):
    result = analyze("https://cassino-demo.example https://shopee.com.br/p", rules, [], [], 1000)
    assert result.status == "critica"
    assert {item["rule"] for item in result.findings} == {"casino", "marketplace"}


@pytest.mark.parametrize("value", ["javascript://evil.example", "https://user:pwd@site.example", "https://site.example:xyz"])
def test_unsafe_url_validation(value):
    with pytest.raises(ValueError):
        canonical_url(value)


def test_unicode_domain_normalization():
    assert normalize_domain("AÇÃO.example") == "xn--ao-siap.example"
