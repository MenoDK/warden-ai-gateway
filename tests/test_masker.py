from ai_core.privacy.masker import PIIMasker, luhn, valid_national_id

masker = PIIMasker()


def test_masks_email_and_reuses_placeholder_for_repeats() -> None:
    result = masker.mask("Write to ana@example.com or ana@example.com, cc bob@example.org")
    assert result.text == "Write to <EMAIL_1> or <EMAIL_1>, cc <EMAIL_2>"
    assert result.entities == {"EMAIL": 2}


def test_unmask_round_trips() -> None:
    original = "Contact ana@example.com about 4111 1111 1111 1111"
    result = masker.mask(original)
    assert "ana@example.com" not in result.text
    assert masker.unmask(result.text, result.mapping) == original


def test_entities_report_types_never_values() -> None:
    result = masker.mask("mail me: ana@example.com")
    assert "ana@example.com" not in repr(result)  # mapping is excluded from repr
    assert "ana@example.com" not in str(result.entities)


def test_national_id_requires_valid_checksum() -> None:
    assert valid_national_id("529.982.247-25")
    assert not valid_national_id("529.982.247-26")
    assert not valid_national_id("111.111.111-11")
    assert masker.mask("id 529.982.247-25").entities == {"NATIONAL_ID": 1}
    # an 11-digit number with a bad checksum is just a number
    assert not masker.mask("order 529.982.247-26").found


def test_card_requires_luhn() -> None:
    assert luhn("4111 1111 1111 1111")
    assert not luhn("4111 1111 1111 1112")
    assert masker.mask("card 4111 1111 1111 1111 ok").entities == {"CARD": 1}
    assert not masker.mask("ref 4111 1111 1111 1112").found


def test_secrets_are_detected() -> None:
    aws = "AK" + "IA" + "ABCDEFGHIJKLMNOP"  # assembled at runtime: no literal key in the repo
    token = "gh" + "p_" + "a" * 36
    result = masker.mask(f"export KEY={aws} and {token}")
    assert result.entities == {"SECRET": 2}
    assert aws not in result.text


def test_phone_and_ip() -> None:
    result = masker.mask("call +55 11 91234-5678 from 192.168.10.7")
    assert result.entities == {"PHONE": 1, "IPV4": 1}


def test_plain_text_is_untouched_and_dates_survive() -> None:
    text = "Meeting on 2026-03-14 about version 3.12.1 and 42 items"
    result = masker.mask(text)
    assert result.text == text
    assert not result.found


def test_overlaps_resolve_by_priority_not_double_masking() -> None:
    # an e-mail local part full of digits must not also be reported as a phone number
    result = masker.mask("user 11912345678@example.com")
    assert result.entities == {"EMAIL": 1}
