# beancount-importer

Importer scripts for beancount

## de.voba-si, Volksbank Siegerland eG, voba-si.de

This folder contains an importer script for "Volksbank Siegerland eG"s statement of
bank account. The scripts runs with statements until the end of June of 2018, when
the banks name in the statement changes, due to the fusion to "Volksbanken in Südwestfalen eG". 
If you want to extract a few months after this date (until end of October 2019), then rewrite
```def identify(self, file)``` to always return true. In October 2019 the PDF version changes 
from 1.3 to 1.7 and this script does not work anymore.  

The script extracts text from the PDF-formatted files and sometimes the end of page
transaction is extracted twice.

## Running scripts

* Make sure, the repo is found by python
```
  export PYTHONPATH="${PYTHONPATH}:$(pwd)"
  echo "PYTHONPATH set: ${PYTHONPATH}"
```
* Configure ```config.py``` to your needs
* Run ```bean-export path/to/config.py path/to/statement.pdf```

## Thank you
* Frank Stollmeier https://github.com/Fjanks/beancount-importer-volksbank
* Michael Blais https://github.com/beancount/beancount
