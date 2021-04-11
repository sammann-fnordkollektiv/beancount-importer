# -*- coding: utf-8 -*-
#
# Beancount importer for PDF exports from Volksbank Siegerland eG.
# Author: Karsten "Sammann" Hiekmann
# License: GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007
#
# https://github.com/beancount/beancount/blob/v2/beancount/ingest/importer.py
# https://github.com/beancount/beancount/blob/v2/beancount/core/data.py


import datetime

import os

import re

from io import StringIO

import locale

from beancount.core.number import D
from beancount.core import data
from beancount.core import amount
from beancount.core import position
from beancount.ingest import importer
from beancount import loader

from pdfminer.high_level import extract_pages
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser


class Volksbank201910Importer(importer.ImporterProtocol):
    """An importer for PDF exports before mid October 2019 from Volksbank online banking ."""

    def __init__(
        self,
        importing_account="Assets:Bank:Volksbank",
        default_adjacent_account="Unknown",
        target_journal=None,
        currency="EUR",
        flag="*",
    ):
        """
        Args:
            importing_account:          string, name of account belonging to the csv export (one leg of the transaction)
            default_adjacent_account:   string, default account to collect the expenses (other leg of the transaction)
            target_journal:             string, optional. Filename of the target journal to guess the corresponding account names instead of using the default_adjacent_account (the other leg of the transaction)
            currency:                   string, optional. Default is 'EUR'
            flag:                       char, optional. Default is '!'
        """
        self.account = importing_account
        self.default_adjacent_account = default_adjacent_account
        self.target_journal = target_journal
        self.currency = currency
        self.flag = flag
        self.file = None

    def identify(self, file):
        self.file = file
        content = content_of(file)
        if "Volksbank Siegerland eG" in content.getvalue():
            return True
        return False

    def extract(self, file):
        self.file = file
        entries = []
        content = content_of(file)
        opening_balance = self.get_balance("ALTER KONTOSTAND", content)
        closing_balance = self.get_balance("NEUER KONTOSTAND", content)
        entries.extend([opening_balance, closing_balance])
        transactions = self.get_transactions(content)
        entries.extend(transactions)
        entries = sorted(entries, key=lambda e: e.date)
        return entries

    def get_balance(self, keyword, content):
        line = get_line_that_contains_x_from_y(keyword, content)
        date, amount_ = get_date_and_amount_from(keyword, line, self.currency)
        balance = create_balance(self.file.name, date, self.account, amount_)
        return balance

    def get_transactions(self, content):
        transactions = []
        regex_date_type_amount_sign = "(\d\d.\d\d.)\s\s(.*)\s([\d.,]*)([+-])[\s]*"
        in_transaction = False
        regex_purpose = "\s{8}(\S.*)"
        year = get_year(content)
        purpose = ""
        for line in content.getvalue().splitlines():
            begin_of_transaction = re.match(regex_date_type_amount_sign, line)
            if begin_of_transaction:
                in_transaction = True
                if purpose:
                    transactions.append(self.transaction_from(amount_, date, purpose))
                    purpose = ""
                date, purpose, amount_ = date_purpose_amount(
                    begin_of_transaction, year, self.currency
                )
            elif in_transaction:
                match = re.match(regex_purpose, line)
                if match:
                    purpose = purpose + " " + match.group(1).strip()
                    purpose = re.sub(" +", " ", purpose)
                else:
                    in_transaction = False
            else:
                in_transaction = False
        return transactions

    def transaction_from(self, amount_, date, purpose):
        second_leg_account = self.default_adjacent_account  # account
        second_leg_flag = "!"

        # Begin transaction customization area
        if "Some defining text" in purpose:
            second_leg_flag = None
            purpose = "Overwrite purpose"
            second_leg_account = "Defining:Account"
        # End transaction customization area

        postings = []
        first_leg = data.Posting(
            self.account,  # account
            amount_,  # amount
            None,  # units
            None,  # price
            None,  # flag
            None,  # meta
        )
        postings.append(first_leg)
        second_leg = data.Posting(
            second_leg_account,  # account
            amount.mul(amount_, D(-1)),  # amount
            None,  # units
            None,  # price
            second_leg_flag,  # flag
            None,  # meta
        )
        postings.append(second_leg)
        transaction = data.Transaction(
            data.new_metadata(self.file.name, 1),  # meta
            date,  # date
            self.flag,  # flag
            " ",  # payee
            purpose,  # narration
            data.EMPTY_SET,  # tags
            data.EMPTY_SET,  # links
            postings,  # postings
        )
        return transaction

    def file_account(self, file):
        self.file = file
        return self.account

    def file_name(self):
        return self.file


def content_of(file):
    content = "not set"
    with open(file.name, "rb") as in_file:
        content = StringIO()
        parser = PDFParser(in_file)
        document = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, content, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(document):
            interpreter.process_page(page)
    return content


def to_datetime_convert(ddmmyyyy):
    """Convert passed argument to datetime.

    Args:
        ddmmyyyy: A date string formatted as follows "dd.mm.yyyy". In example '01.01.1970'
    Returns:
        datetime
    """
    day, month, year = ddmmyyyy.replace('"', "").split(".")
    return datetime.date(int(year), int(month), int(day))


def get_line_that_contains_x_from_y(keyword, content):
    found = ""
    for line in content.getvalue().splitlines():
        if keyword in line:
            found = line
            break
    return found


def get_date_and_amount_from(keyword, content, currency):
    """Extract date and amount from content.

    Args:
        content: String content from a PDF export
    Returns:
        Array with datetime and amount, else empty
    """
    regex = ".*" + keyword + ".*(\d\d.\d\d.\d\d\d\d).*EUR\s*(.*)([+-])"
    match = re.match(regex, content)
    ddmmyyyy = match.group(1)
    amount_ = match.group(2)
    sign = match.group(3)
    date = to_datetime_convert(ddmmyyyy)
    amount_ = to_amount_convert(amount_, sign, currency)
    return date, amount_


def to_amount_convert(amount_, sign, currency):
    """Convert passed arguments to amount.Amount

     Args:
        amount_: de_DE-localized Monetray value, in example "1.337,42"
        sign: Extracted + or -
    Returns:
        amount.Amount
    """
    amount_ = amount_.replace(".", "").replace(",", ".")
    if sign == "-":
        amount_ = "-" + amount_
    amount_ = amount.Amount(D(str(amount_)), currency)
    return amount_


def create_balance(filename, date, account, amount_):
    balance = data.Balance(
        data.new_metadata(filename, ""),  # metadata
        date,  # date
        account,  # account
        amount_,  # amount
        None,  # tolerance
        None,  # diff_amount
    )
    return balance


def get_year(content):
    line = get_line_that_contains_x_from_y("KONTOAUSZUG", content)
    year = line.strip()[-4:]
    return year


def date_purpose_amount(match, year, currency):
    date = to_datetime_convert(match.group(1) + year)
    purpose = match.group(2).strip()
    amount_ = match.group(3)
    sign = match.group(4)
    amount_ = to_amount_convert(amount_, sign, currency)
    return date, purpose, amount_
