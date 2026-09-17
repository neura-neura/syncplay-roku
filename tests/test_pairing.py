from bridge.pairing import Pairing


def test_pairing_single_use_expiry_attempts(monkeypatch):
    p=Pairing()
    code=p.create()['code']
    assert len(code)==6 and code.isdigit()
    assert p.redeem(code)
    assert not p.redeem(code)
    code=p.create()['code']
    p.expires=0
    assert not p.redeem(code)
    code=p.create()['code']
    for _ in range(5):
        assert not p.redeem('bad')
    assert not p.redeem(code)
    code=p.create()['code']
    assert p.redeem(code)
