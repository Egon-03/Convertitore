"""Auto-test dell'app impacchettata (uso interno della build, non visibile all'utente).

    ConvertiTutto.exe --autotest <cartella campioni> <cartella uscita> <file resoconto>

Prova tutte le conversioni proposte per ogni file della cartella campioni usando
il programma installato, così si scoprono i moduli dimenticati da PyInstaller.
"""

from __future__ import annotations

import os
import time
import traceback

from . import engine, formats


def run(samples: str, out_root: str, report: str) -> int:
    ok = fail = 0
    f = open(report, "w", encoding="utf-8", buffering=1)  # riga per riga: utile se una conversione si blocca

    class _Lines:
        def append(self, line: str) -> None:
            f.write(line + "\n")

    lines = _Lines()
    for name in sorted(os.listdir(samples)):
        src = os.path.join(samples, name)
        try:
            kind = formats.detect(src)
        except Exception as e:  # noqa: BLE001
            fail += 1
            lines.append(f"FAIL {name:28} riconoscimento: {type(e).__name__}: {e}")
            continue
        for t in kind.recommended + kind.more:
            out = os.path.join(out_root, name.replace(".", "_"))
            t0 = time.time()
            try:
                res = engine.convert(engine.Job(src, t, out, {}))
                for r in res:
                    if not os.path.isdir(r) and os.path.getsize(r) == 0:
                        raise RuntimeError("file vuoto")
                ok += 1
                lines.append(f"OK   {name:28} -> {t.title:22} {time.time() - t0:5.1f}s")
            except Exception as e:  # noqa: BLE001
                fail += 1
                first = (str(e).strip().splitlines() or [type(e).__name__])[0][:150]
                lines.append(f"FAIL {name:28} -> {t.title:22} {type(e).__name__}: {first}")
                if not isinstance(e, engine.ConversionError):
                    lines.append("     " + traceback.format_exc().replace("\n", "\n     "))
    lines.append(f"\nRiuscite: {ok}  Fallite: {fail}")
    f.close()
    return 0 if fail == 0 else 1
