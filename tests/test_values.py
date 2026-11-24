from brvm_extract.values import cell_flag, parse_date, parse_int, parse_number


def test_french_numbers():
    assert parse_number("1 234,56") == 1234.56
    assert parse_number("-7,45 %") == -7.45
    assert parse_number("13 276 985 405 819") == 13276985405819
    assert parse_number("6.50") == 6.5          # dot decimal inside a French bulletin
    assert parse_number("1 806,") == 1806       # first half of a number split over two lines


def test_english_numbers():
    assert parse_number("1,234.56", "en") == 1234.56
    assert parse_number("24,000", "en") == 24000
    assert parse_number("0.07", "en") == 0.07
    assert parse_number("9,995", "fr", comma_thousands=True) == 9995  # order-book prices


def test_empty_and_flags():
    for s in ("", "-", "NC", "ND", "SP", None, "NT"):
        assert parse_number(s) is None
    assert cell_flag("NC") == "NC"
    assert cell_flag("SP") == "SP"
    assert cell_flag("NT") == "NC"
    assert parse_int("2 388") == 2388


def test_dates():
    import datetime as dt
    assert parse_date("18-août-25") == "2025-08-18"
    assert parse_date("10-sept.-25") == "2025-09-10"
    assert parse_date("17 May 24") == "2024-05-17"
    assert parse_date("29/10/2025") == "2025-10-29"
    assert parse_date("11/03/19") == "2019-03-11"
    assert parse_date("11-oct", dt.date(2017, 1, 2)) == "2017-10-11"      # no year: next occurrence
    assert parse_date("06-mars", dt.date(2017, 6, 1)) == "2018-03-06"
    assert parse_date("28 mars/ 28 sep.") is None                          # coupon period, not a date


def test_fetch_shares_parse():
    import fetch_shares
    html = """<table><tr><th>Code obligation</th><th>Nom</th><th>Nombre de titres</th><th>Cours du jour</th>
      <th>Capitalisation flottante</th><th>Capitalisation globale</th><th>Capitalisation globale (%)</th></tr>
      <tr><td>SNTS</td><td>SONATEL  SENEGAL</td><td>1 000 000 000</td><td>3 900</td><td>85 800 000 000</td>
          <td>3 900 000 000 000</td><td>20,87</td></tr></table>"""
    rows = fetch_shares.parse(html)
    assert rows == [{"symbol": "SNTS", "name": "SONATEL SENEGAL", "shares": 1e9, "price": 3900.0,
                     "float_cap": 85.8e9, "global_cap": 3.9e12}]
    try:
        fetch_shares.check(rows)          # one stock only: rejected as an incomplete page
        raise AssertionError("an incomplete page must be rejected")
    except ValueError:
        pass
