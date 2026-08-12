from __future__ import annotations

from pathlib import Path

from backend.app.services.extraction import extract_holerite_pages
from backend.app.services.pdf import read_pdf
from backend.app.services.pdf.models import PdfPage


EXAMPLES = Path(__file__).parents[2] / "exemplos"


def test_corporate_layout_preserves_fields_bases_and_brazilian_strings(make_page):
    page = make_page(
        [
            [("Mês/Ano:", 10), ("8/2018", 100)],
            [("Verba", 10), ("Nome", 100), ("Base", 250), ("Valor", 350)],
            [
                ("803", 10),
                ("PREVI", 70),
                ("PESSOAL", 110),
                ("PB2", 170),
                ("6.188,63", 260),
                ("-433,20", 360),
            ],
            [("010", 10), ("VENCIMENTO", 70), ("PADRAO-VP", 150), ("3.059,94", 360)],
            [("Proventos Bruto:", 10), ("6.188,63", 180), ("Valor Líquido:", 280), ("4.351,55", 390)],
        ],
        width=500,
    )

    result = extract_holerite_pages((page,))["pages"][0]

    assert (result["year"], result["month"]) == ("2018", "08")
    assert result["fields"] == [
        {
            "code": "803",
            "label": "PREVI PESSOAL PB2",
            "reference": "6.188,63",
            "value": "-433,20",
        },
        {
            "code": "010",
            "label": "VENCIMENTO PADRAO-VP",
            "reference": "",
            "value": "3.059,94",
        },
    ]
    assert result["bases"] == [
        {"label": "Proventos Bruto", "value": "6.188,63"},
        {"label": "Valor Líquido", "value": "4.351,55"},
    ]


def test_visual_receipt_header_extracts_fields_without_codes(make_page):
    page = make_page(
        [
            [("Recibo de Pagamento", 100)],
            [("Referência", 100), ("SETEMBRO/2019", 200)],
            [("Proventos", 100), ("Descontos", 300)],
            [
                ("Descrição", 10),
                ("Qtde", 140),
                ("Valor", 200),
                ("Descrição", 260),
                ("Qtde", 390),
                ("Valor", 450),
            ],
            [("SALARIO", 10), ("1.300,00", 200), ("INSS MES", 260), ("200,43", 450)],
            [
                ("TOTAL DE PROVENTOS", 10),
                ("1.300,00", 200),
                ("TOTAL DE DESCONTOS", 260),
                ("200,43", 450),
            ],
            [("LIQUIDO A RECEBER", 260), ("1.099,57", 450)],
        ],
        width=550,
    )

    result = extract_holerite_pages((page,))["pages"][0]

    assert result["fields"] == [
        {"code": "", "label": "SALARIO", "reference": "", "value": "1.300,00"},
        {"code": "", "label": "INSS MES", "reference": "", "value": "200,43"},
    ]
    assert all("code" not in base for base in result["bases"])
    assert {base["label"] for base in result["bases"]} == {
        "TOTAL DE PROVENTOS",
        "TOTAL DE DESCONTOS",
        "LIQUIDO A RECEBER",
    }


def test_empty_physical_page_and_input_page_order_are_preserved(make_page):
    empty = PdfPage(7, 400, 800, (), "embedded")
    payroll = make_page(
        [
            [("Mês/Ano:", 10), ("1/2020", 100)],
            [("Verba", 10), ("Nome", 100), ("Base", 250), ("Valor", 350)],
            [("010", 10), ("SALARIO", 70), ("2.389,77", 360)],
        ],
        page_number=3,
        width=500,
    )

    pages = extract_holerite_pages((empty, payroll))["pages"]

    assert [page["page"] for page in pages] == [7, 3]
    assert pages[0] == {
        "page": 7,
        "year": "",
        "month": "",
        "fields": [],
        "bases": [],
    }
    assert pages[1]["month"] == "01"


def test_real_financial_sheet_keeps_multiple_blocks_on_same_physical_page():
    pages = read_pdf(EXAMPLES / "payroll-01.pdf")

    result = extract_holerite_pages(pages)["pages"]
    first_page_blocks = [block for block in result if block["page"] == 1]

    assert [(block["year"], block["month"]) for block in first_page_blocks] == [
        ("2017", "04"),
        ("2017", "05"),
        ("2017", "06"),
        ("2017", "07"),
        ("2017", "08"),
        ("2017", "09"),
    ]
    assert {
        field["label"]
        for block in first_page_blocks
        for field in block["fields"]
    }.isdisjoint({"REMUNERAÇÃOMES", "DIAS/HORASTRAB"})
    assert {
        "code": "40",
        "label": "Reembolso VR",
        "reference": "0,00",
        "value": "360,00",
    } in first_page_blocks[0]["fields"]

    december_thirteenth_salary = next(
        block
        for block in result
        if block["page"] == 2
        and block["month"] == "12"
        and len(block["fields"]) > 30
    )
    assert {
        "code": "512",
        "label": "INSS 13o. Sal",
        "reference": "0",
        "value": "347,46",
    } in december_thirteenth_salary["fields"]


def test_real_sap_layout_preserves_slash_prefixed_codes():
    page = read_pdf(EXAMPLES / "payroll-03.pdf")[0]

    fields = extract_holerite_pages((page,))["pages"][0]["fields"]

    assert {
        "code": "/314",
        "label": "Contr. INSS Remuneração",
        "reference": "9,00",
        "value": "177,03",
    } in fields
    assert {
        "code": "/B02",
        "label": "Adiantamento pago",
        "reference": "",
        "value": "671,44",
    } in fields


def test_real_scan_with_sparse_court_stamp_uses_ocr_and_deduplicates_vias():
    pages = read_pdf(EXAMPLES / "payroll-04.pdf")

    result = extract_holerite_pages(pages)["pages"]

    assert all(page.source == "ocr" for page in pages)
    assert len(result) == len(pages) == 5
    assert (result[0]["year"], result[0]["month"]) == ("2019", "09")
    assert {
        "code": "",
        "label": "SALARIO",
        "reference": "",
        "value": "953,36",
    } in result[0]["fields"]
    assert all("TOTAL" not in field["label"] for field in result[0]["fields"])
