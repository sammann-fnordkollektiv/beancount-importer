import beancount_importer_de_voba_si

CONFIG = [
    beancount_importer_de_voba_si.Volksbank201910Importer(
        importing_account = "Assets:Bank:Volksbank",
        default_adjacent_account="Expenses:Außerordentlich:UnklareAusgabeVomVolksbankkonto",
        target_journal = "journal-volksbank.beancount",
        currency = "EUR",
        flag = "*"
        )
    ]

