# -*- python -*-

from piksi_tools.utils import Time


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


def test_time_sub():
    t6 = Time(1, 400)
    t7 = Time(2, 500)
    t8 = (t7 - t6)
    # confirm positive subraction result makes sense
    assert t8 == Time(1, 100)
    # adding then subtracking t6 should cancel out back to t7
    assert (t8 + t6) == t7
    # confirm negative result makes sense
    t9 = t6 - t7
    assert t9 == Time(-2, 900)
    # TODO: result for t9 maybe should be normalized to -1 -100 in the util
    # But at the very least float representation should match
    assert t8.to_float() == -t9.to_float()
    # adding then subtracking t7 should cancel out back to t6
    assert (t9 + t7) == t6
    # Confirm identity property of addition / subtraction
    assert t8 + t9 == Time(0, 0)
    # Confirm adding negative number is equivalent to subtracting positive number
    t10 = Time(-1, -100)
    t11 = Time(1,  100)
    assert (t7 + t10) == Time(1, 400)
    assert (t7 - t11) == Time(1, 400)


def test_time_to_float():
    t6 = Time(1, 400)
    t6.to_float() -1.4 <= 0.00001


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


def test_time_le():
    t1 = Time(1, 500)
    t2 = Time(1, 500)
    assert t1 <= t2
    t2 += Time(0, 1)
    assert t1 <= t2
    t1 += Time(0, 2)
    assert not (t1 <= t2)


def test_time_lt():
    t1 = Time(1, 500)
    t2 = Time(1, 500)
    assert not (t1 > t2)
    t1 += Time(0, 1)
    assert (t2 < t1)

def test_time():
    t1 = Time.now()
    t2 = Time.now()
    # For epoch time, seconds will "never" be zero
    assert (    ((t1._seconds == 0 and t1._millis != 0) or (t1._seconds != 0))
            and ((t2._seconds == 0 and t2._millis != 0) or (t2._seconds != 0))
            and (t1._millis != 0 or t2._millis != 0)) # Could land on 0 milliseconds, but probably never twice


def test_iter():
    t1 = Time(1, 500)
    t2 = Time(1, 505)
    ls = [Time(1, 501), Time(1, 502), Time(1, 503), Time(1, 504), Time(1, 505)]
    for iter_t in Time.iter_since(t1, t2):
        assert ls.pop(0) == iter_t
    assert len(ls) == 0
