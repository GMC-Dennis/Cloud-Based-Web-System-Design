import pytest

from app.modules.identity.domain.entities import InvalidPhoneNumber, PhoneNumber


def test_accepts_e164_style_number():
    assert str(PhoneNumber("+254712345678")) == "+254712345678"


def test_accepts_number_without_plus():
    assert str(PhoneNumber("254712345678")) == "254712345678"


@pytest.mark.parametrize("bad", ["", "abc", "12", "++254712345678", "071"])
def test_rejects_invalid_numbers(bad):
    with pytest.raises(InvalidPhoneNumber):
        PhoneNumber(bad)
