from app.utils import generate_room_code, normalize_room_code


def test_generate_room_code_length_and_alphabet():
    code = generate_room_code()
    assert len(code) == 6
    assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in code)


def test_normalize_room_code():
    assert normalize_room_code(" k7m2pq ") == "K7M2PQ"
    assert normalize_room_code("K7-M2-PQ") == "K7M2PQ"
