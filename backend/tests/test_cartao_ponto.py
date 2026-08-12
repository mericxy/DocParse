from __future__ import annotations

from backend.app.services.extraction.cartao_ponto import (
    extract_cartao_ponto_pages,
    normalize_time_hhmm,
)
from backend.app.services.pdf.models import BoundingBox, PdfPage, PdfWord


def test_extracts_rows_in_document_order_and_keeps_day_without_punches(make_page):
    page = make_page(
        [
            [("Data", 10), ("Entrada", 110), ("Saída", 180), ("Observação", 260)],
            [("21/05/2019", 10), ("08:25", 115), ("18:25", 185)],
            [("19/05/2019", 10)],
            [("22/05/2019", 10), ("8:05", 115), ("12:00", 155), ("13:00", 195)],
        ]
    )

    result = extract_cartao_ponto_pages((page,))

    assert result == {
        "pages": [
            {
                "page": 1,
                "days": [
                    {
                        "date_raw": "21/05/2019",
                        "punches": [
                            {"kind": "IN", "time_raw": "08:25", "time_hhmm": "08:25"},
                            {"kind": "OUT", "time_raw": "18:25", "time_hhmm": "18:25"},
                        ],
                    },
                    {"date_raw": "19/05/2019", "punches": []},
                    {
                        "date_raw": "22/05/2019",
                        "punches": [
                            {"kind": "IN", "time_raw": "8:05", "time_hhmm": "08:05"},
                            {"kind": "OUT", "time_raw": "12:00", "time_hhmm": "12:00"},
                            {"kind": "IN", "time_raw": "13:00", "time_hhmm": "13:00"},
                        ],
                    },
                ],
            }
        ]
    }


def test_attaches_visual_continuation_punches_to_the_same_day(make_page):
    page = make_page(
        [
            [("Dia", 15), ("Ent1", 120), ("Sai1", 180), ("H.Ext", 260)],
            [("01/05/2025", 15), ("08:00", 120), ("12:00", 180)],
            [("13:00", 120), ("17:00", 180)],
            [("02/05/2025", 15)],
        ]
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [punch["time_raw"] for punch in days[0]["punches"]] == [
        "08:00",
        "12:00",
        "13:00",
        "17:00",
    ]
    assert days[1] == {"date_raw": "02/05/2025", "punches": []}


def test_does_not_attach_undated_incompatible_line_to_previous_day(make_page):
    page = make_page(
        [
            [("Data", 15), ("Ent1", 120), ("Sai1", 180), ("H.Ext", 260)],
            [("01/05/2025", 15), ("08:00", 120), ("12:00", 180)],
            [("Observação", 15), ("13:00", 120), ("17:00", 180)],
            [("02/05/2025", 15)],
        ]
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [punch["time_raw"] for punch in days[0]["punches"]] == ["08:00", "12:00"]
    assert days[1] == {"date_raw": "02/05/2025", "punches": []}


def test_merges_only_an_adjacent_repeated_day_label(make_page):
    page = make_page(
        [
            [("Dia", 15), ("Ent1", 120), ("Sai1", 180)],
            [("01", 15), ("08:00", 120), ("12:00", 180)],
            [("01", 15), ("13:00", 120), ("17:00", 180)],
            [("02", 15)],
            [("01", 15)],
        ]
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [day["date_raw"] for day in days] == ["01", "02", "01"]
    assert [punch["time_raw"] for punch in days[0]["punches"]] == [
        "08:00",
        "12:00",
        "13:00",
        "17:00",
    ]


def test_merges_adjacent_repeated_day_used_only_for_auxiliary_continuation(make_page):
    page = make_page(
        [
            [("Dia", 15), ("Entrada", 120), ("Saída", 180), ("Ocorrência", 260)],
            [("23", 15), ("09:24", 120), ("18:57", 180), ("HE-BCO", 265)],
            [("23", 15), ("HE-REMUNERADA", 265)],
            [("24", 15)],
        ]
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [day["date_raw"] for day in days] == ["23", "24"]
    assert [punch["time_raw"] for punch in days[0]["punches"]] == ["09:24", "18:57"]


def test_repeated_date_with_incompatible_geometry_starts_new_record():
    raw_words = [
        ("Data", 10, 20),
        ("Entrada", 110, 20),
        ("Saída", 180, 20),
        ("01/05/2025", 10, 40),
        ("08:00", 110, 40),
        ("12:00", 180, 40),
        ("01/05/2025", 10, 180),
        ("13:00", 110, 180),
        ("17:00", 180, 180),
        ("02/05/2025", 10, 200),
    ]
    words = tuple(
        PdfWord(
            text=text,
            bbox=BoundingBox(x0, y0, x0 + max(20, len(text) * 6), y0 + 10),
            page=1,
            block=sequence,
            line=sequence,
            word=0,
            sequence=sequence,
            source="ocr",
        )
        for sequence, (text, x0, y0) in enumerate(raw_words)
    )
    page = PdfPage(1, 400, 800, words, "ocr")

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [day["date_raw"] for day in days] == ["01/05/2025", "01/05/2025", "02/05/2025"]


def test_header_coordinates_are_discovered_instead_of_fixed(make_page):
    page = make_page(
        [
            [("Dia", 140), ("Entrada", 310), ("Saida", 420), ("Falta", 520)],
            [("03/06/2025", 140), ("09:10", 315), ("18:20", 425)],
        ],
        width=650,
    )

    day = extract_cartao_ponto_pages((page,))["pages"][0]["days"][0]

    assert day["date_raw"] == "03/06/2025"
    assert [punch["time_raw"] for punch in day["punches"]] == ["09:10", "18:20"]


def test_ocr_words_on_one_baseline_define_complete_header_and_stop_column():
    raw_words = [
        ("Data", 10, 20),
        ("Ent1", 110, 20),
        ("Sai1", 170, 20),
        ("H.Ext", 240, 20),
        ("01/05/2025", 10, 40),
        ("08:00d", 110, 40),
        ("17:00d", 170, 40),
        ("01:00", 250, 40),
    ]
    words = tuple(
        PdfWord(
            text=text,
            bbox=BoundingBox(x0, y0, x0 + max(20, len(text) * 6), y0 + 10),
            page=1,
            block=sequence,
            line=sequence,
            word=0,
            sequence=sequence,
            source="ocr",
        )
        for sequence, (text, x0, y0) in enumerate(raw_words)
    )
    page = PdfPage(1, 400, 800, words, "ocr")

    day = extract_cartao_ponto_pages((page,))["pages"][0]["days"][0]

    assert day == {
        "date_raw": "01/05/2025",
        "punches": [
            {"kind": "IN", "time_raw": "08:00d", "time_hhmm": "08:00"},
            {"kind": "OUT", "time_raw": "17:00d", "time_hhmm": "17:00"},
        ],
    }


def test_isolated_fallback_infers_columns_from_page_content(make_page):
    page = make_page(
        [
            [("01/07/2025", 80), ("07:30", 240), ("16:30", 320)],
            [("02/07/2025", 80)],
        ],
        width=500,
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert days == [
        {
            "date_raw": "01/07/2025",
            "punches": [
                {"kind": "IN", "time_raw": "07:30", "time_hhmm": "07:30"},
                {"kind": "OUT", "time_raw": "16:30", "time_hhmm": "16:30"},
            ],
        },
        {"date_raw": "02/07/2025", "punches": []},
    ]


def test_fallback_excludes_clearly_separated_auxiliary_time(make_page):
    page = make_page(
        [
            [
                ("01/01/2025", 20),
                ("08:00", 150),
                ("12:00", 210),
                ("13:00", 270),
                ("17:00", 330),
                ("01:30", 520),
            ],
            [("02/01/2025", 20)],
        ],
        width=650,
    )

    day = extract_cartao_ponto_pages((page,))["pages"][0]["days"][0]

    assert [punch["time_raw"] for punch in day["punches"]] == [
        "08:00",
        "12:00",
        "13:00",
        "17:00",
    ]


def test_pages_are_not_reordered(make_page):
    page_7 = make_page(
        [[("Data", 10), ("Entrada", 110)], [("02/01/2025", 10), ("09:00", 115)]],
        page_number=7,
    )
    page_3 = make_page(
        [[("Data", 10), ("Entrada", 110)], [("01/01/2025", 10), ("08:00", 115)]],
        page_number=3,
    )

    result = extract_cartao_ponto_pages((page_7, page_3))

    assert [page["page"] for page in result["pages"]] == [7, 3]


def test_time_normalization_is_conservative():
    assert normalize_time_hhmm("8:05") == "08:05"
    assert normalize_time_hhmm("08:05") == "08:05"
    assert normalize_time_hhmm("0?:25") == "0?:25"
    assert normalize_time_hhmm("13:9?") == "13:9?"
    assert normalize_time_hhmm("??:30") == "??:30"
    assert normalize_time_hhmm("29:80") == "??:??"
    assert normalize_time_hhmm("07:00d") == "07:00"
    assert normalize_time_hhmm("+03:00d") == "03:00"
    assert normalize_time_hhmm("14:56c") == "14:56"
    assert normalize_time_hhmm("08:25x") == "08:25x"


def test_date_raw_is_preserved_literally_even_when_impossible(make_page):
    page = make_page(
        [
            [("Data", 10), ("Entrada", 110)],
            [("38/07/2025", 10), ("08:00", 115)],
            [("10/13/2025", 10)],
            [("31/02/2025", 10)],
            [("0?/05/2025", 10)],
        ]
    )

    days = extract_cartao_ponto_pages((page,))["pages"][0]["days"]

    assert [day["date_raw"] for day in days] == [
        "38/07/2025",
        "10/13/2025",
        "31/02/2025",
        "0?/05/2025",
    ]
