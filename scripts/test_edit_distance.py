import pytest
from scripts.haiku_ocr_cleanup import edit_distance, MAX_CHANGE_RATIO

def test_edit_distance_identical():
    assert edit_distance("hello", "hello") == 0

def test_edit_distance_empty():
    assert edit_distance("", "") == 0
    assert edit_distance("abc", "") == 3
    assert edit_distance("", "abc") == 3

def test_edit_distance_simple():
    assert edit_distance("kitten", "sitten") == 1
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance("flaw", "lawn") == 2

def test_edit_distance_within_threshold():
    # Length 100, max change 15% + 10 = 25
    s1 = "a" * 100
    s2 = "a" * 100 + "b" * 20
    assert edit_distance(s1, s2) == 20
    assert edit_distance(s2, s1) == 20

def test_edit_distance_exceed_threshold():
    # Length 10, max change 15% + 10 = 11.5
    s1 = "a" * 10
    s2 = "a" * 10 + "b" * 15
    # If it exceeds, it should at least be consistent and ideally return a large enough value
    d1 = edit_distance(s1, s2)
    d2 = edit_distance(s2, s1)
    assert d1 >= 10
    assert d2 >= 10
    # The current implementation might fail this if it's not symmetric
    assert d1 == d2

def test_edit_distance_order_independence():
    s1 = "kitten"
    s2 = "sitting"
    assert edit_distance(s1, s2) == edit_distance(s2, s1)

if __name__ == "__main__":
    pytest.main([__file__])
