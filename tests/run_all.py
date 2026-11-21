"""Prova tutte le conversioni proposte per ogni file di esempio."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from convertitutto import engine, formats

samples, out_root = sys.argv[1], sys.argv[2]
only = sys.argv[3:] or None
ok = fail = 0
for name in sorted(os.listdir(samples)):
    if only and not any(o in name for o in only):
        continue
    src = os.path.join(samples, name)
    kind = formats.detect(src)
    for t in kind.recommended + kind.more:
        out = os.path.join(out_root, name.replace(".", "_"))
        t0 = time.time()
        try:
            res = engine.convert(engine.Job(src, t, out, {}))
            sizes = []
            for r in res:
                if os.path.isdir(r):
                    sizes.append(f"[cartella {len(os.listdir(r))} file]")
                else:
                    assert os.path.getsize(r) > 0, "file vuoto"
                    sizes.append(formats.human_size(os.path.getsize(r)))
            ok += 1
            print(f"OK   {name:28} → {t.title:22} {time.time() - t0:5.1f}s  {', '.join(sizes)}")
        except Exception as e:
            fail += 1
            print(f"FAIL {name:28} → {t.title:22} {type(e).__name__}: {str(e).splitlines()[0][:110]}")
print(f"\nRiuscite: {ok}  Fallite: {fail}")
