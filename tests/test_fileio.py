# -*- python -*-

from piksi_tools.fileio import Time


def test_time_repr():
    t1 = Time(1, 0)
    assert repr(t1) == "Time(s=1,ms=0)"


def test_time_eq():
    t1 = Time(1, 0)
    t2 = Time(2, 0)
    assert t1 != t2
    t3 = Time(1, 0)
    assert t1 == t3


def test_time_add():
    t4 = Time(1, 500)
    t5 = Time(1, 500)
    assert (t4 + t5) == Time(3, 0)


def test_time_ge():
    t4 = Time(1, 500)
    t5 = Time(1, 500)
    assert t4 >= t5
    t4 += Time(0, 1)
    assert t4 >= t5
    t5 += Time(0, 2)
    assert not (t4 >= t5)


def test_time_gt():
    t4 = Time(1, 500)
    t5 = Time(1, 500)
    assert not (t4 > t5)
    t4 += Time(0, 1)
    assert (t4 > t5)


def test_time():
    t1 = Time.now()
    t2 = Time.now()
    # For epoch time, seconds will "never" be zero
    assert t1._seconds != 0 and t2._seconds != 0
    # Could land on 0 milliseconds, but probably never twice
    assert t1._millis != 0 or t2._millis != 0


def test_iter():
    t1 = Time(1, 500)
    t2 = Time(1, 505)
    ls = [Time(1, 501), Time(1, 502), Time(1, 503), Time(1, 504), Time(1, 505)]
    for iter_t in Time.iter_since(t1, t2):
        assert ls.pop(0) == iter_t
    assert len(ls) == 0
