"""Avvio di ConvertiTutto. Accetta i file da convertire come argomenti (menu del tasto destro)."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) == 5 and sys.argv[1] == "--autotest":  # solo per la verifica della build
        from convertitutto import selftest
        sys.exit(selftest.run(*sys.argv[2:5]))
    from convertitutto.ui import run
    sys.exit(run(sys.argv))
