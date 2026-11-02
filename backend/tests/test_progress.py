from findme.progress import EtaCalculator, progress_event


def feed(calc, t0, rate, seconds, start_done=0):
    done = start_done
    for s in range(seconds + 1):
        done = start_done + int(rate * s)
        calc.observe(t0 + s, done)
    return done


def test_not_confident_early():
    c = EtaCalculator()
    c.observe(0.0, 0)
    c.observe(2.0, 20)
    r = c.compute(2.0, 20, 100)
    assert not r.confident and r.eta_sec is None


def test_not_confident_below_ten_pct():
    c = EtaCalculator()
    feed(c, 0.0, 0.5, 15)
    r = c.compute(15.0, 7, 100)
    assert not r.confident


def test_not_confident_while_workers_initializing():
    c = EtaCalculator()
    done = feed(c, 0.0, 10, 15)
    r = c.compute(15.0, done, 300, workers_initializing=1)
    assert not r.confident


def test_confident_constant_rate_eta_close():
    c = EtaCalculator()
    done = feed(c, 0.0, 10, 15)
    r = c.compute(15.0, done, 300, workers_initializing=0)
    assert r.confident
    expected = (300 - done) / 10
    assert abs(r.eta_sec - expected) <= 5
    assert r.eta_sec % 5 == 0


def test_rate_change_recovery():
    c = EtaCalculator()
    done = feed(c, 0.0, 2, 40)
    done = feed(c, 41.0, 20, 40, start_done=done)
    r = c.compute(81.0, done, 2000)
    assert r.confident
    assert 15 <= r.rate <= 25


def test_event_shape():
    c = EtaCalculator()
    done = feed(c, 0.0, 10, 15)
    eta = c.compute(15.0, done, 300)
    ev = progress_event(7, "embedding", done, 300, 517, eta, {"initializing": 0, "running": 2})
    assert ev["seq"] == 7
    assert ev["pct"] == round(done / 3, 1)
    assert ev["etaConfident"] is True
    assert ev["workers"]["running"] == 2
