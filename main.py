"""Avvio di ConvertiTutto. Accetta i file da convertire come argomenti (menu del tasto destro)."""

import multiprocessing
import sys

from convertitutto.ui import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(run(sys.argv))
