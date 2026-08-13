"""ตัวรันเทสต์สำรองสำหรับเครื่องที่ยังไม่ได้ติดตั้ง pytest

**ใช้ pytest เป็นหลักเสมอ** - สคริปต์นี้มีไว้ตรวจงานเร็ว ๆ ในสภาพแวดล้อม
ที่ลง dependency ไม่ได้เท่านั้น มันรองรับแค่ส่วนของ pytest ที่เทสต์ชุด
ปัจจุบันใช้จริง (fixture ตามชื่อ, pytest.raises, tmp_path, autouse fixture)
ไม่ใช่ตัวแทนของ pytest

    python tools/run_tests_nopytest.py
"""

import importlib.util
import inspect
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
TMP = Path(tempfile.mkdtemp(prefix="sieng-tests-"))


class _Raises:
    def __init__(self, exc, match=None):
        self.exc, self.match, self.value = exc, match, None

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if t is None:
            raise AssertionError(f"ไม่ได้โยน {self.exc.__name__}")
        if not issubclass(t, self.exc):
            return False
        if self.match and not re.search(self.match, str(v)):
            raise AssertionError(f"ข้อความไม่ตรงกับ {self.match!r}: {v}")
        self.value = v
        return True


class _PytestShim:
    @staticmethod
    def raises(exc, match=None):
        return _Raises(exc, match)

    class mark:
        security = staticmethod(lambda f: f)
        slow = staticmethod(lambda f: f)
        vectors = staticmethod(lambda f: f)

        @staticmethod
        def parametrize(names, cases):
            keys = [n.strip() for n in names.split(",")]

            def deco(fn):
                fn._params = (keys, cases)
                return fn

            return deco

    @staticmethod
    def fixture(*a, **k):
        def deco(fn):
            fn._is_fixture = True
            return fn

        return deco(a[0]) if a and callable(a[0]) else deco


sys.modules["pytest"] = _PytestShim  # type: ignore[assignment]


class _TmpFactory:
    def mktemp(self, name: str) -> Path:
        d, i = TMP / name, 0
        while d.exists():
            i += 1
            d = TMP / f"{name}{i}"
        d.mkdir(parents=True)
        return d


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"{path.stem}_{abs(hash(path))}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> int:
    tests_dir = ROOT / "tests"
    conf = _load(tests_dir / "conftest.py")
    fixtures = {
        n: f for n, f in vars(conf).items()
        if callable(f) and getattr(f, "_is_fixture", False)
    }
    cache: dict[str, object] = {"tmp_path_factory": _TmpFactory()}
    counter = [0]

    def resolve(name: str):
        if name == "tmp_path":
            counter[0] += 1
            d = TMP / f"case{counter[0]}"
            d.mkdir(parents=True, exist_ok=True)
            return d
        if name in cache:
            return cache[name]
        fn = fixtures[name]
        val = fn(*[resolve(p) for p in inspect.signature(fn).parameters])
        if inspect.isgenerator(val):
            val = next(val)
        cache[name] = val
        return val

    resolve("_container")

    passed, failures = 0, []
    for f in sorted(tests_dir.rglob("test_*.py")):
        mod = _load(f)
        local_fixtures = {
            n: fn for n, fn in vars(mod).items()
            if getattr(fn, "_is_fixture", False) and not n.startswith("_")
        }
        fixtures.update(local_fixtures)
        autouse = [
            fn for n, fn in vars(mod).items()
            if getattr(fn, "_is_fixture", False) and n.startswith("_")
        ]
        for name, fn in sorted(vars(mod).items()):
            if not (name.startswith("test_") and callable(fn)):
                continue
            gens = []
            try:
                for a in autouse:
                    g = a()
                    if inspect.isgenerator(g):
                        next(g)
                        gens.append(g)
                params = getattr(fn, "_params", None)
                if params:
                    keys, cases = params
                    for case in cases:
                        vals = case if isinstance(case, tuple) else (case,)
                        kw = dict(zip(keys, vals))
                        rest = [resolve(p) for p in inspect.signature(fn).parameters
                                if p not in kw]
                        fn(*rest, **kw)
                        passed += 1
                    passed -= 1
                else:
                    fn(*[resolve(p) for p in inspect.signature(fn).parameters])
                passed += 1
            except Exception as e:  # noqa: BLE001
                failures.append((f.name, name, f"{type(e).__name__}: {e}"))
            finally:
                for g in gens:
                    try:
                        next(g)
                    except StopIteration:
                        pass

    print(f"\nผ่าน {passed} · ล้มเหลว {len(failures)}")
    for file, test, err in failures:
        print(f"  FAIL {file}::{test}\n       {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
