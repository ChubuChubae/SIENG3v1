# SIENG3 — Project Context & Work Scope

> **อ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง** แล้วเข้างานต่อได้เลยโดยไม่ต้องไล่อ่านโค้ดทั้งโปรเจกต์
> ไฟล์นี้ตอบ 4 คำถาม: ตอนนี้อยู่ที่ไหน · ตกลงกันไว้ว่าอะไร · ต้องทำอะไรต่อ · อะไรยังไม่ได้ตัดสินใจ
> อ้างอิงสถาปัตยกรรม: `docs/PROJECT_STRUCTURE.md` (v1.2)
> อัปเดตล่าสุด: 2026-08-12

---

## 1. สถานะปัจจุบัน

### 1.1 สรุปในหนึ่งย่อหน้า

โฟลเดอร์โปรเจกต์คือ **`SIENG3v1`** (เปลี่ยนชื่อมาจาก `SIENG2_2`)
สถานะคือ **skeleton ที่ Phase 0 เสร็จแล้ว** — โครงครบทั้ง 41 แพ็กเกจตาม `PROJECT_STRUCTURE.md`
ชั้น `app` `ui` มีโค้ดจริงที่รันได้ ส่วนชั้น `carrier` `domain` `cost` `coder` `crypto` `pipeline` `analyzer`
ยังมีแต่ `__init__.py` ที่บรรจุ docstring บอกหน้าที่และข้อห้ามของชั้นนั้น
โค้ดเดิม (GUI, analyzer, stego, crypto ~16,800 บรรทัด) ถูกลบโดยเจตนา เพื่อเริ่มเขียนใหม่ตามสัญญาของแต่ละชั้น

### 1.2 ตัวเลขจริง

| รายการ | จำนวน |
|---|---:|
| แพ็กเกจ Python ใน `src/sieng` | 41 |
| ไฟล์ `.py` ใน `src/sieng` | 45 ไฟล์ / 458 บรรทัด (Phase 0 เพิ่ม `app` กับ `ui` เข้ามา) |
| ไฟล์ test | 13 ไฟล์ / 393 บรรทัด — **34 test ผ่านหมด** |
| ไฟล์ทรัพยากร | 88 (svg 43 · png 38 · qss 1 · yaml 5 · c 1) |
| `pip install -e .` | ผ่านแล้ว (มี `src/sieng.egg-info/`) |
| `nox` ชุดมาตรฐาน 6 session | **ผ่านหมด** — lint · types · imports (4 contracts kept) · unit 86 · vectors · security 9+1 skip |
| git | repo ใหม่ commit เดียว `ADD: Create Skeleton Project` |

### 1.3 อะไรมีอยู่ อะไรไม่มี

| มีอยู่แล้ว | สภาพ |
|---|---|
| `src/sieng/app/` `ui/gui/bootstrap.py` `ui/cli/__main__.py` | **โค้ดจริงที่รันได้** จาก Phase 0.3 |
| `src/sieng/common/` | Phase 2.1 — exception hierarchy 14 ตัว · `RedactingFilter` · `ProgressReporter.scoped()` |
| `src/sieng/domain/` | Phase 2.2 — `Plane` (**freeze แล้ว**) · `build_changeable_mask` · `permute` · capacity |
| `src/sieng/carrier/` | Phase 3 ครบ — `Carrier` ABC · `CarrierRegistry` · `sniff` จาก magic · **`PngCarrier` และ `JpegCarrier` byte-exact** |

**สิ่งที่ spike ค้นพบและกลายเป็นข้อบังคับของ `_jpeg_codec.py`**

libjpeg 6b เก็บ coefficient ได้ครบทุก byte แต่เขียน header ต่างจากต้นฉบับ 3 จุด — APP0 ซ้ำ (+18 B),
component id ใน SOF และ SOS เปลี่ยนจากฐาน 1 เป็นฐาน 0 ทั้งหมดเป็น metadata ที่คนเทียบกับต้นฉบับเห็นได้
`splice()` จึงประกอบไฟล์เอง: **header ของต้นฉบับทั้งดุ้น + entropy data ใหม่**
และมี `verify_tables_match()` กันกรณีที่ libjpeg เขียน DQT/DHT ใหม่ตอนแก้ coefficient
ซึ่งจะทำให้ entropy data ถอดด้วยตารางเดิมไม่ได้ — เจอแล้วต้องหยุด ไม่ใช่ปล่อยไฟล์ที่ถอดออกมาเป็นขยะ
| `tests/fixtures/` | 10 ไฟล์ 431 KiB — png 4 แบบ · jpg QF 50/75/95 · progressive · ไฟล์ที่ต้องถูกปฏิเสธ · สร้างซ้ำได้ด้วย `make_fixtures.py` |
| `tools/spike_jpeglib.py` | สคริปต์ตอบ D1 — ต้องรันบน Windows ก่อนเขียน Phase 3.3 |
| `src/sieng/**/__init__.py` | docstring อธิบายหน้าที่ + ข้อห้ามของแต่ละชั้น · 5 ไฟล์มี `# TODO(skeleton):` บอกว่าต้อง export อะไรกลับมา |
| `noxfile.py` `scripts/check.sh` `scripts/check.ps1` | ชุดตรวจ 15 session รันในเครื่อง |
| `.gitignore` `.gitattributes` | ignore cache/build artifact · บังคับ line ending เป็น LF |
| `src/sieng/ui/gui/assets/` | ไอคอน svg 43 + png 38 (ซ้ำกันเกือบทั้งหมด — ควรเหลือ svg) |
| `src/sieng/ui/gui/styles/default.qss` | ธีมมืด ใช้ได้เลย |
| `src/sieng/pipeline/yaml/templates/*.yaml` | 5 เทมเพลต — **อ้าง engine ที่ยังไม่มี และ 2 ไฟล์อ้าง mp3 ที่นอกสโคป** |
| `src/sieng/coder/_native/stc_kernel.c` | ยังไม่ได้ตรวจว่าใช้ได้จริง |
| `tests/` 13 ไฟล์ | 34 test ครอบโค้ด Phase 0 · โฟลเดอร์ `vectors` `property` `integration` `fuzz` ยังว่างรอเฟสของมัน |
| `docs/` | `PROJECT_STRUCTURE.md` · **`THREAT_MODEL.md` · `SESSION_PROTOCOL.md` · `FORMAT_SPEC.md`** (Phase 1) · ไฟล์นี้ |
| `research/` | `README.md`, `datasets/split.py`, `stats.py` |
| `tools/` | `spike_jpeglib.py` — ตรวจว่า jpeglib ยังทำตัวตามที่ `_jpeg_codec.py` สมมติไว้ |
| `pyproject.toml` `requirements.txt` `README.md` `SECURITY.md` `main.py` | ตรวจแล้ว ติดตั้งได้จริง |

| ยังไม่มี |
|---|
| โค้ดทำงานของ `carrier`, `domain`, `cost`, `coder`, `crypto`, `pipeline`, `analyzer` และหน้าจอจริงของ `ui` |
| fixture ภาพตัวอย่าง · lockfile |

**ต้องทำบนเครื่อง Windows เอง** — sandbox ที่ผมใช้แก้ `.git/` ไม่ได้ (`index.lock` ลบไม่ออก)

```
git rm -r --cached src/sieng.egg-info    # build artifact ที่หลุดเข้า commit แรก
git add --renormalize .                  # ให้ .gitattributes มีผลย้อนหลัง แก้ CRLF
git add .gitignore .gitattributes
git commit -m "chore: ignore build artifacts and normalise line endings"
```

### 1.3.1 Phase 0 — ทำไปแล้วอะไรบ้าง

| ไฟล์ | ทำอะไร |
|---|---|
| `README.md` | ใหม่ — `pyproject.toml` อ้างถึงแต่ไฟล์ไม่มี ทำให้ `pip install -e .` พังทันที |
| `pyproject.toml` | เพิ่ม `jpeglib` · `liboqs-python` · `detect-secrets` · ปิด RUF001-003 (คอมเมนต์ไทย) · per-file-ignore ของ noxfile |
| `requirements.txt` | sync กับ pyproject · เพิ่ม `detect-secrets` แทน gitleaks |
| `noxfile.py` | ใหม่ — 15 session · ชุด default = `lint types imports unit vectors security` |
| `scripts/check.sh` · `check.ps1` | ใหม่ — เรียกชุดมาตรฐานในคำสั่งเดียว |
| `src/sieng/app/settings.py` | ใหม่ — frozen dataclass + validate ช่วงค่า + อ่าน env/TOML · คีย์ที่สะกดผิดต้อง error ไม่ใช่ถูกละเลย |
| `src/sieng/app/container.py` | ใหม่ — composition root พร้อม hook ลงทะเบียน 3 จุด (Phase 3.1 / 6.1 / 8.1) |
| `src/sieng/ui/gui/bootstrap.py` | ใหม่ — เปิดหน้าต่างเปล่า · import PyQt6 แบบ lazy ให้ test ที่ไม่เกี่ยว GUI ไม่พัง |
| `src/sieng/ui/cli/__main__.py` | ใหม่ — ปลายทางของ console script `sieng` · คำสั่งที่ยังไม่พร้อมคืน exit 3 ไม่ใช่ 0 |
| `main.py` | จับ `GuiUnavailableError` แล้วพิมพ์ข้อความสั้นแทน traceback |
| `src/sieng/_deferred/` | ลบตาม D8 |
| `tests/**` | ลบของเดิมตาม D7 แล้วเขียนใหม่ให้ครอบโค้ด Phase 0 — **34 test** ใน 5 ไฟล์ (`conftest` + unit 4 + security 1) ตามกฎ §2.2 "ทุกไฟล์ใหม่ต้องมี test" |

**ผลการรัน `nox` รอบแรกและสิ่งที่แก้**

| Session | ปัญหาที่เจอ | แก้อย่างไร |
|---|---|---|
| `lint` | RUF022 — `__all__` ใน `sieng/__init__.py` ไม่ได้เรียง | เรียงเป็น `["CRYPTO_SUITE", "__version__"]` |
| `imports` | `include_external_packages` ไม่ได้เปิด ทั้งที่มี contract ห้าม `torch` ซึ่งเป็นแพ็กเกจนอก | เปิดใน `[tool.importlinter]` |
| `unit` `vectors` `security` | pytest คืน exit 5 = ไม่มี test ให้เก็บ (ลบไปตาม D7) | เขียน test ของ Phase 0 · เพิ่ม `_pytest()` ใน noxfile ที่ยอม exit 5 **เฉพาะโฟลเดอร์ที่ประกาศไว้ว่ายังไม่ถึงเฟส** พร้อม warn ทุกครั้ง |
| `types` | ผ่านตั้งแต่รอบแรก | — |

`tests/unit` กับ `tests/security` **ไม่อยู่ในรายการที่ยอมให้ว่าง** โดยเจตนา — สองอันนี้เป็นเกณฑ์ปิด module ตาม §2.5 การปล่อยให้ผ่านทั้งที่ไม่มี test คือการโกหกตัวเอง
`tests/vectors` `property` `integration` `fuzz` ยอมให้ว่างได้ พร้อมข้อความบอกว่าจะมี test จริงตอน Phase ไหน

### 1.4 สภาพแวดล้อม

| รายการ | ค่า | หมายเหตุ |
|---|---|---|
| Python บนเครื่อง sandbox | **3.10.12** | เอกสารกำหนด **3.11+** — ต้องเลือกว่าจะลด requirement หรืออัปเกรด |
| OS dev หลัก | Windows 11 | STC native kernel ต้อง build ได้บน Windows |
| Docker | จำเป็นสำหรับ analyzer | ยังไม่ได้ทดสอบ |

---

## 2. ข้อตกลงในการทำงาน

ข้อตกลงพวกนี้ **ไม่ต้องถามซ้ำ** ทำตามได้เลย ถ้าจะฝ่าฝืนต้องคุยก่อน

### 2.1 กฎการ import (บังคับด้วย `import-linter` ในสคริปต์ตรวจ)

| กฎ | เหตุผล |
|---|---|
| `crypto/**` import ได้เฉพาะ `common` | ต้อง audit ชั้นนี้แบบแยกเดี่ยวได้ |
| `ui/**` ห้าม import `crypto`, `coder`, `cost` ตรงๆ | GUI ไม่ควรมีโอกาสถือคีย์ดิบ — ผ่าน `pipeline` เท่านั้น |
| `domain/**` import ได้เฉพาะ `common` | เป็นชั้นล่างสุดของสายข้อมูล |
| `src/sieng/**` ห้าม import `torch` ทั้งทางตรงและทางอ้อม | ผู้ใช้ทั่วไปต้องติดตั้งได้บนเครื่องธรรมดา |
| ห้าม circular import ทุกกรณี | — |

ตารางเต็มอยู่ใน `PROJECT_STRUCTURE.md` §2.2

### 2.2 กฎการเขียนโค้ด

| กฎ | รายละเอียด |
|---|---|
| **Fail closed** | capacity ไม่พอ / AAD ไม่ตรง / header เสีย → ยกเลิกทั้งงาน **ห้าม fallback ไปวิธีที่อ่อนกว่าโดยเงียบ** |
| **ไม่มี magic string ในสิ่งที่ฝัง** | ทุก bit ที่ลงไปในภาพต้องแยกจากค่าสุ่มไม่ออก · magic ใช้ได้เฉพาะในไฟล์แยก (`.sess`) |
| **`costs()` ห้ามขึ้นกับ payload หรือคีย์** | ถ้าขึ้น การกระจายตัวของการแก้ค่าจะรั่วข้อมูลเป็น side channel |
| **JPEG ห้าม re-compress** | เข้า-ออกที่ระดับ quantized coefficient เท่านั้น ห้ามผ่าน `Image.open().save()` |
| **error ของการถอดรหัสต้องเหมือนกันหมด** | ข้อความเดียว เวลาเท่ากัน ไม่แยกสาเหตุ |
| ทุกไฟล์ใหม่ต้องมี test | ไม่มี test = ยังไม่เสร็จ |

### 2.2.1 สไตล์การเขียนโค้ด

โค้ด Phase 0 ทั้งหมดเขียนตามสไตล์นี้แล้ว ใช้เป็นตัวอ้างอิงได้เลย โดยเฉพาะ
`src/sieng/app/settings.py` (production) และ `tests/unit/test_settings.py` (test)

#### ภาษาและรูปแบบไฟล์

| กฎ | รายละเอียด |
|---|---|
| **คำอธิบายในโค้ดเป็นภาษาอังกฤษทั้งหมด** | docstring · คอมเมนต์ · ข้อความ error · ชื่อ import-linter contract · pytest marker |
| **ไฟล์ `.py` ต้องเป็น ASCII ล้วน** | ห้ามใช้ `—` `★` `·` `→` แม้ในคอมเมนต์ · ruff เปิด `RUF001-003` ไว้ตรวจแล้ว (ภาษาไทยใช้ได้เฉพาะใน `docs/*.md`) |
| **ไม่ใช้ `from __future__ import annotations`** | โปรเจกต์กำหนด Python 3.11+ ไวยากรณ์ใหม่ใช้ได้ตรงๆ อยู่แล้ว |
| **บรรทัดยาวไม่เกิน 100 ตัวอักษร** | นับเป็นตัวอักษร ไม่ใช่ byte (`line-length = 100`) |
| **ห้ามจัดคอมเมนต์ท้ายบรรทัดให้ตรงคอลัมน์** | `ruff format` บีบเหลือ 2 ช่องเสมอ — เขียน `VALUE = 10  # note` ไม่ใช่ `VALUE = 10      # note` |
| **`raise ... from error` ทุกครั้งที่อยู่ใน `except`** | ทำให้ traceback แยกออกว่า error มาจาก input ที่ผิด หรือมาจากบั๊กในโค้ดที่จัดการ error เอง |
| **ห้าม implicit Optional** | `config_path: Path \| None = None` ไม่ใช่ `config_path: Path = None` |
| **path ปลอมใน test ใช้ `/fake/...` ไม่ใช่ `/tmp/...`** | สื่อว่าไม่มีการแตะดิสก์จริง และไม่ไปชน `S108` ที่ยังต้องเปิดไว้ตรวจโค้ดจริง |

#### Type hint

ใส่เท่าที่ช่วยให้เข้าใจ ไม่ใช่ใส่ให้ครบ

```python
def load_stylesheet(name: str = DEFAULT_STYLE):     # ใส่ที่ param เมื่อชนิดไม่ชัดจากชื่อ
def run(container):                                  # ไม่ใส่เมื่อชื่อบอกอยู่แล้ว
def load_settings(config_path: Path = None, **overrides):
```

ห้ามใช้ `-> None`, `ClassVar`, `TYPE_CHECKING`, `dict[str, Any]` ในโค้ดทั่วไป

**ข้อยกเว้น — ชั้นที่ `mypy --strict` ตรวจต้องใส่ annotation ให้ครบทุกตัว**
`crypto/` `coder/` `carrier/` `domain/` และ **`common/`** เพราะ mypy ตามเข้าไปตรวจโมดูลที่ชั้นพวกนั้น import
ถ้า `common/` ไม่มี annotation `disallow_untyped_calls` จะฟ้องทุกครั้งที่ `domain` เรียกมัน
(`strict` ตั้งไว้ที่ระดับ global ใน `pyproject.toml` เพราะ **mypy ไม่รองรับ `strict` ใน per-module section**
ขอบเขตที่ถูกตรวจจริงกำหนดด้วย path ที่ `noxfile.py` ส่งเข้าไป)

#### Docstring

**บรรทัดเดียวถ้าพอ** ขยายเป็นย่อหน้าที่สองเฉพาะตอนที่ต้องอธิบายเหตุผล

```python
def load_stylesheet(name: str = DEFAULT_STYLE):
    """Return the theme, or an empty string. A missing theme should not block startup."""


def run(container):
    """Open the GUI and return an exit code.

    PyQt6 is imported here so this module still imports without the [gui] extra,
    which keeps non-GUI tests from failing on a missing dependency.
    """
```

| หลัก | ตัวอย่างจริงในโค้ด |
|---|---|
| อธิบาย **ทำไม** ไม่ใช่ **ทำอะไร** | `"""PyQt6 is missing. The message must say how to fix it, not just that it broke."""` |
| ยกตัวอย่าง input/output จริง | `เช่น SIENG_LOG_LEVEL=debug จะได้ {"log_level": "DEBUG"}` |
| บอกผลที่ตามมาถ้าทำผิด | `"""Silence here means running on defaults while believing the config was applied."""` |

#### ข้อความ error

ยาวได้ ต้องบอกครบสามอย่าง: **ผิดตรงไหน · ค่าที่ยอมรับคืออะไร · ทำอะไรต่อ**

```python
raise SettingsError(
    f"Invalid default_stc_height={self.default_stc_height}: "
    f"must be between {low} and {high} "
    f"(higher = better coding efficiency but exponentially slower)"
)

raise GuiUnavailableError(
    'PyQt6 is not installed. Run: pip install -e ".[gui]" '
    "(or use the CLI instead: sieng --status)"
)
```

ข้อยกเว้นเดียว: **`DecryptError` ต้องเป็นข้อความเดียวเสมอ** ไม่แยกสาเหตุ ไม่ให้ timing ต่างกัน (§2.2)

#### โครงสร้างโค้ด

| กฎ | รายละเอียด |
|---|---|
| **ชื่อตัวแปรบอกความหมาย** | `current_context` ไม่ใช่ `ctx` · `matched` ไม่ใช่ `m` · `error` ไม่ใช่ `e` |
| **ไม่แตกฟังก์ชันย่อยเกินจำเป็น** | logic ที่อ่านต่อเนื่องกันให้อยู่ด้วยกัน แตกเมื่อมีคนเรียกซ้ำจริง หรือยาวจนอ่านไม่ไหว |
| **ไม่ใส่ `_` นำหน้าถ้าอ่านแล้วเข้าใจ** | `read_env()` `read_toml()` ไม่ใช่ `_from_env()` `_read_toml()` |
| **`try/except` ครอบเฉพาะบรรทัดที่เสี่ยง** | แล้ว raise ต่อด้วย exception ของโปรเจกต์พร้อมบริบทที่ผู้ใช้ต้องรู้ |
| **ค่าคงที่ระดับโมดูลเป็น UPPER_CASE จัดกลุ่มพร้อมคอมเมนต์** | `DEFAULT_STC_HEIGHT` `ENV_PREFIX` `STC_HEIGHT_RANGE` |
| **import ข้างในฟังก์ชันเมื่อมีเหตุผล** | dependency ที่เป็น optional (`PyQt6`), ของที่มาทีหลัง (`tomllib`), หรือกันไม่ให้ผิดกฎ layering |

#### Test

```python
pytestmark = pytest.mark.usefixtures("clean_env")


# ---- validation ------------------------------------------------------------


@pytest.mark.parametrize("height", [5, 15, 0, -1])
def test_stc_height_outside_range_is_rejected(height):
    with pytest.raises(SettingsError, match="default_stc_height"):
        make_settings(default_stc_height=height)


def test_with_overrides_leaves_the_original_alone():
    settings = load_settings()

    changed = settings.with_overrides(log_level="DEBUG")

    assert changed.log_level == "DEBUG"
    assert settings.log_level == "INFO"
```

| กฎ | รายละเอียด |
|---|---|
| **ใช้ `assert` ตรงๆ** | ไม่ห่อ helper ที่ซ่อนสิ่งที่กำลังตรวจ |
| **ชื่อฟังก์ชันอ่านเป็นประโยคได้** | `test_misspelled_config_key_is_an_error` ไม่ใช่ `test_config_1` |
| **เว้นบรรทัดแยก arrange / act / assert** | เห็นได้ทันทีว่าบรรทัดไหนคือสิ่งที่กำลังทดสอบ |
| **docstring เฉพาะตอนที่ต้องบอกว่าทำไมเคสนี้สำคัญ** | `"""This cap blocks a forged counter. At 0 the receiver can never decrypt anything."""` |
| **`# ---- หัวข้อ ----` คั่นกลุ่ม** | เมื่อไฟล์มีหลายด้าน เช่น defaults / validation / where values come from |
| **`parametrize` สำหรับกวาดค่า** | ค่าขอบและค่านอกช่วงอยู่คนละ test กัน |
| **`pytestmark` สำหรับ fixture ที่ทั้งไฟล์ต้องใช้** | ไม่ต้องใส่ซ้ำทุกฟังก์ชัน |

### 2.3 กฎการเปลี่ยน format / crypto

**ห้ามแก้ของเดิมทับ — เพิ่ม suite ใหม่แล้วขึ้นเลขเสมอ**
แก้ `crypto/kdf/labels.py` หรือ `header.py` ทับลงไป = ไฟล์ที่ฝังไว้แล้วทั้งหมดถอดไม่ได้อีกเลย
ขั้นตอนอยู่ใน `PROJECT_STRUCTURE.md` §8.4

### 2.4 กฎเรื่องสโคป

| | |
|---|---|
| **Carrier ของ Phase 1 มีแค่ `.jpg` และ `.png`** | ไฟล์อื่นต้องโยน `UnsupportedCarrierError` ห้ามเดา ห้าม fallback |
| Analyzer สโคปกว้างกว่า (รวม wav/avi) | เป็นคนละหน้าที่ — ตรวจไฟล์ที่คนอื่นส่งมา |
| UI ต้องแสดงนามสกุลที่รองรับ **คนละชุด** ระหว่างหน้า analyze กับหน้า embed | กันผู้ใช้เข้าใจว่า "วิเคราะห์ .wav ได้ = ฝังใน .wav ได้" |
| ห้ามเพิ่มถาวร | network transport · anti-forensics |
| ห้ามเพิ่มในเฟสนี้ | H.264/video embedding · cloud · database · AI adaptive stego |

### 2.5 กฎการทำงานร่วมกัน

- **ถามก่อนลบหรือเขียนทับไฟล์ที่มีอยู่**
- **ห้ามปิด module** ถ้า `vectors` (KAT) หรือ `security` test ไม่ผ่าน
- ปิด module แล้วอัปเดตช่อง Status ในหัวข้อ 4 ของไฟล์นี้
- เจอ crash จาก fuzzing → เก็บเข้า `tests/fuzz/corpus/` เป็น regression ถาวร
- **สำรองงานเองก่อนทำอะไรที่ย้อนกลับไม่ได้** — โปรเจกต์นี้ไม่มีระบบกู้คืนอัตโนมัติ

### 2.6 การตรวจสอบ — รันในเครื่องทั้งหมด

**โปรเจกต์นี้ไม่พึ่งบริการภายนอกใดๆ ในการตรวจสอบ** ทุกอย่างรันในเครื่องด้วย `nox`

| คำสั่ง | ตรวจอะไร | รันเมื่อไหร่ |
|---|---|---|
| `nox -s lint types imports` | ruff · mypy --strict · import-linter | ทุกครั้งที่แก้โค้ดเสร็จ |
| `nox -s unit` | unit test | ทุกครั้งที่แก้โค้ดเสร็จ |
| `nox -s property` | hypothesis — คุณสมบัติที่ต้องจริงกับทุก input ไม่ใช่แค่ค่าที่เราคิดถึง | ทุกครั้งที่แก้ `domain` `coder` `carrier` |
| `nox -s vectors` | **KAT ทั้งหมด** | **ต้องผ่านก่อนปิด module เสมอ ห้ามข้าม** |
| `nox -s security` | negative test (MITM · rollback · concurrency · leak) | **ต้องผ่านก่อนปิด module เสมอ** |
| `nox -s sast secrets deps` | bandit + semgrep · detect-secrets · pip-audit | เมื่อแตะ dependency หรือ crypto |
| `nox -s integration` | pipeline ครบวงจร + template yaml | ก่อนปิด phase |
| `nox -s fuzz-smoke` | fuzz 60 วินาที/target | ก่อนปิด phase |
| `nox -s sbom image-scan` | SBOM · trivy | ก่อน release |
| `scripts/check.ps1` / `check.sh` | เรียกชุดตรวจมาตรฐานทั้งหมดในคำสั่งเดียว | ใช้เป็นค่าเริ่มต้น |

**เหตุผลที่เลือกแบบนี้:** โค้ดชุดนี้จัดการคีย์และไฟล์ที่ผู้ใช้ถือว่าเป็นความลับ การส่งโค้ดกับ artifact ขึ้นบริการภายนอกเพิ่มพื้นที่โจมตีและข้อผูกมัดที่ไม่จำเป็นกับงานวิจัย — และการตรวจในเครื่องทำให้ผลที่ได้ตรงกับสภาพเครื่องที่ใช้พัฒนาจริงมากกว่า

**ผลที่ตามมาที่ต้องยอมรับ:** ไม่มีอะไรบังคับให้การตรวจถูกรันจริง — **วินัยของคนเขียนคือกลไกเดียวที่มี** ถ้าวันหนึ่งมีคนทำงานร่วมกันหลายคนแล้วเรื่องนี้เป็นปัญหา ให้กลับมาทบทวนข้อนี้ใหม่

---

## 3. ภาพรวม Phase

แบ่งตามชั้น dependency — แต่ละ phase ทำได้จริงเพราะของที่มันพึ่งพาเสร็จก่อนแล้ว

| Phase | ชื่อ | ขึ้นกับ | ผลลัพธ์ที่จับต้องได้ |
|:---:|---|---|---|
| **0** | Project setup | — | `pip install -e .` ผ่าน · `nox` ผ่านครบทุก session · lockfile |
| **1** | Protocol specification | 0 | เอกสาร P0 สามฉบับ — **บล็อกทุก phase ที่เหลือ** |
| **2** | Foundation: common + domain | 0 | `Plane` + error hierarchy + logging ที่กันคีย์หลุด |
| **3** | Carrier: jpeg + png | 2 | เปิด-เขียน JPEG กลับได้ byte-exact |
| **4** | Analyzer (นำโค้ดเดิมกลับ) | 2, 3 | วิเคราะห์ไฟล์ได้ครบเหมือนเดิม + DCT module ใหม่ |
| **5** | Coder: STC | 2 | ฝัง/ถอด bit ตาม cost vector ได้ |
| **6** | Cost models | 2, 3 | J-UNIWARD / HILL คืน cost map ที่ตรง reference |
| **7** | Crypto | 1, 2 | session + ratchet + AEAD + header ที่ผ่าน KAT |
| **8** | Pipeline + engines | 3, 5, 6, 7 | `sieng embed` / `sieng extract` ทำงานครบวงจร |
| **9** | UI (นำโค้ดเดิมกลับ + ต่อสายใหม่) | 4, 8 | GUI ใช้งานได้ |
| **10** | Research evaluation | 3, 5, 6 | ตาราง P_E + CI ตาม 4 มิติ |
| **11** | Hardening + release | ทั้งหมด | sandbox · fuzz · SBOM · release manifest |

**เส้นทางที่สั้นที่สุดไปสู่ "ฝังได้จริง":** 0 → 1 → 2 → 3 → 5 → 6 → 7 → 8
Phase 4 (analyzer) กับ 9 (ui) เป็นการนำโค้ดเดิมกลับ ทำขนานไปกับสายหลักได้ถ้ามีคนสองคน

---

## 4. Scope งานแยกตาม Module

รูปแบบของทุก module: **ไฟล์ที่ต้องสร้าง → ขึ้นกับ → DoD (เกณฑ์ว่าเสร็จ) → test ที่ต้องผ่าน**
ช่อง Status: `☐` ยังไม่เริ่ม · `◐` กำลังทำ · `☑` เสร็จ

---

### Phase 0 — Project Setup

#### 0.1 Packaging ☐

**ไฟล์:** `pyproject.toml` (ตรวจ/แก้), `requirements.txt` (ตรวจ/แก้), `requirements.lock` หรือ `uv.lock`
**ขึ้นกับ:** —
**DoD**
- `pip install -e ".[gui,analyzer,dev]"` ผ่านบน Windows และ Linux
- ลบ `requirements.txt` ตัวเก่า (encoding UTF-16 ทำ `pip install -r` พังบางเครื่อง)
- optional group แยก `[gui]` `[analyzer]` `[research]` `[dev]` — `torch` อยู่ใน `[research]` เท่านั้น
- `requirements.txt` กับ `pyproject.toml` ตรงกันทุกตัว (ไฟล์ทั้งสองประกาศกฎนี้ไว้เอง)
- ตัดสินใจเรื่อง Python 3.10 vs 3.11 แล้วบันทึกลง `pyproject.toml`

**Test:** `python -c "import sieng; print(sieng.__version__)"` ผ่านหลังติดตั้ง

#### 0.2 Tooling & local checks ☐

> **ทุกการตรวจรันในเครื่องด้วยคำสั่งเดียว ไม่พึ่งบริการภายนอก**

**ไฟล์:** `noxfile.py`, `scripts/check.ps1` + `scripts/check.sh`, `.importlinter`, config ของ ruff/mypy ใน `pyproject.toml`
**ขึ้นกับ:** 0.1
**DoD**
- `nox` มี session ครบ: `lint` `types` `imports` `sast` `secrets` `deps` `unit` `vectors` `security` — ผ่านทั้งหมดบน skeleton
- `scripts/check.ps1` (Windows) และ `scripts/check.sh` (Linux) เรียก `nox` ตัวเดียวจบ
- `import-linter` บังคับตารางใน §2.1 ได้จริง (ลองใส่ import ผิดกฎแล้วต้องแดง)
- `mypy --strict` ผ่านบน `crypto` `coder` `carrier` `domain`
- `nox -s security` และ `nox -s vectors` **ต้องแยกเป็น session ของตัวเอง** เพื่อให้ใช้เป็นเกณฑ์ปิด module ได้ตามกฎใน §2.5

**Test:** `nox` รันในเครื่องเปล่าแล้วผ่านครบทุก session

#### 0.3 Entry point ☐

**ไฟล์:** `main.py` (ลดเหลือ ~5 บรรทัด), `src/sieng/ui/gui/bootstrap.py`, `src/sieng/app/settings.py`, `src/sieng/app/container.py`
**ขึ้นกับ:** 0.1
**DoD**
- `main.py` ไม่มี logic เหลือ — เรียก `bootstrap` เท่านั้น
- `Settings` อ่านจาก env / ไฟล์ / default ได้ และ `frozen=True`
- `build_container()` เป็นที่เดียวในระบบที่ประกอบ registry
- `python main.py` ขึ้น window เปล่าได้ (ยังไม่มีหน้า)

**Test:** `test_container_builds_with_defaults`

---

### Phase 1 — Protocol Specification (P0 · บล็อกทุกอย่าง)

> **ห้ามเขียนโค้ด `crypto/` บรรทัดแรกก่อน phase นี้เสร็จ** — การเปลี่ยนใจในเอกสารมีต้นทุนเป็นชั่วโมง ในโค้ดที่ปล่อยไปแล้วมีต้นทุนเป็นการทำลาย backward compatibility ทั้งหมด

#### 1.1 `docs/THREAT_MODEL.md` ☐

**ขึ้นกับ:** —
**DoD**
- ตารางฝ่ายตรงข้าม 9 ราย ระบุชัดว่าใครอยู่ในและนอกขอบเขต
- แยกคำศัพท์ให้ครบ: forward secrecy · post-compromise security · key compromise · state compromise
- ตาราง scenario × protection ที่บอกตรงๆ ว่าอะไรป้องกันไม่ได้
- ประกาศชัดว่า **memory compromise และ endpoint compromise อยู่นอกขอบเขต**
- ระบุ known gaps 6 ข้อ (§11.3 ของ `PROJECT_STRUCTURE.md`)

**Test:** ทบทวนกับ `PROJECT_STRUCTURE.md` §2.6 — ต้องไม่ขัดกัน

#### 1.2 `docs/SESSION_PROTOCOL.md` ☐

**ขึ้นกับ:** 1.1
**DoD**
- ลำดับ handshake ครบทุกขั้นตอน พร้อมสิ่งที่แต่ละฝ่ายรู้ในแต่ละขั้น
- นิยาม `AUTH_IMPLICIT` (HPKE auth mode, overhead 0 B) และ `AUTH_PQ_EXPLICIT` (+3,373 B)
- **สูตร transcript แบบตายตัว พร้อม length-prefix ทุกฟิลด์** และเหตุผลว่าทำไมต้องมี
- ระบุขั้นตอนที่ผู้ใช้เทียบ fingerprint กันนอกระบบ — GUI ต้องบังคับ ไม่ใช่ dialog ที่กดผ่าน
- ประกาศตรงๆ ว่า `AUTH_IMPLICIT` ให้ classical authentication + PQ confidentiality และเหตุผลว่าทำไมพอสำหรับ threat model นี้

#### 1.3 `docs/FORMAT_SPEC.md` ☐

**ขึ้นกับ:** 1.2
**DoD**
- layout ระดับ bit ของ header 12 B / 16 B รวม flag ทุก bit
- layout ของ `SessionEnvelope` ทั้งโหมด external (มี magic) และ inline (ไม่มี magic)
- **ตารางความจุจริง** พร้อมเกณฑ์ที่ `choose_mode()` ใช้ตัดสิน (envelope ≈ 1.2–4.6 KB vs ภาพ 512×512 ที่ 0.1 bpnzAC ≈ 325 B)
- ลำดับการ derive คีย์ทั้งหมดพร้อม label string
- **ระบุว่า `K_hdr_session` derive จาก `ss` ไม่ใช่จาก `MK[n]`** พร้อมเหตุผลเรื่องวงจรไก่กับไข่
- ตัดสินใจแล้วว่า header เป็น 12 B หรือ 16 B

**Test:** เขียน pseudo-code แล้วเดินตามเอกสารได้จนจบโดยไม่ต้องเดา

---

### Phase 2 — Foundation

#### 2.1 `common/` ☐

**ไฟล์:** `errors.py`, `logging.py`, `progress.py`, `types.py`
**ขึ้นกับ:** —
**DoD**
- exception hierarchy ครบตาม `PROJECT_STRUCTURE.md` §4.10 — `SiengError` เป็นราก
- `DecryptError` มีข้อความเดียว ไม่รับ detail เข้ามาได้ตั้งแต่ระดับ signature
- `RedactingFilter` ตัดค่าที่ดูเหมือนคีย์/nonce/ciphertext ออกจาก log ทุกระดับ
- `ProgressReporter.scoped(lo, hi)` แบ่งช่วง % ให้ subtask ได้ (แก้ปัญหาโค้ดเดิมที่มี `update_progress()` ซ้ำ 3 ไฟล์)
- พึ่งพา stdlib เท่านั้น

**Test:** `test_no_secret_appears_in_logs` · `test_progress_scoped_never_exceeds_100`

#### 2.2 `domain/` ☐

**ไฟล์:** `plane.py`, `selection.py`, `capacity.py`
**ขึ้นกับ:** 2.1
**DoD**
- `Plane` มี `values`, `changeable`, `meta` + `flatten()` / `unflatten()` / `n_changeable()`
- `build_changeable_mask()` — DCT เลือกเฉพาะ non-zero AC (`skip_dc=True`) · spatial เลือกทั้งหมด
- `permute(n, seed)` เป็น **argsort บน keystream ของ SHAKE256** — ผลลัพธ์เหมือนกันทุกแพลตฟอร์มและทุกเวอร์ชัน
  (เปลี่ยนจากที่เคยเขียนไว้ว่า ChaCha20 + Fisher-Yates ด้วยเหตุผลสองข้อ: `domain` ห้ามพึ่ง crypto primitive
  ตามกฎ import §2.1 และ **numpy ไม่รับประกันความเข้ากันได้ข้ามเวอร์ชันของ `Generator`** ซึ่งลำดับนี้ต้องคงที่
  ตราบเท่าที่ยังมีไฟล์ stego อยู่ · algorithm อยู่ในโค้ดเราเอง ไม่ฝากไว้กับไลบรารี)
- `bits_from_bpnzac()` / `bpnzac_from_bits()` / `max_payload_bits()`
- **ห้าม import อะไรนอกจาก `common`**

> **★ freeze `plane.py` หลัง phase นี้** — แก้ทีหลังกระทบทุกชั้นตั้งแต่ 5 ลงมา (§6.2)

**Test:** `tests/unit/test_domain.py` (มีอยู่แล้ว) · `test_permute_is_deterministic_across_platforms` · `test_dc_is_never_changeable`

---

### Phase 3 — Carrier Layer

#### 3.1 `carrier/base.py` + `registry.py` + `errors.py` ☐

**ขึ้นกับ:** 2.2
**DoD**
- `Carrier` ABC ครบตาม §4.2 · `domain` เป็น `Literal["dct", "spatial"]`
- `security_tier` ยังเป็น Literal 3 ค่าแม้ Phase 1 มีแต่ `strong` (กลไกเตือนต้องพร้อมก่อน Phase 2)
- `CarrierRegistry.for_domain()` ให้ UI สร้าง dropdown ได้ โดย UI ไม่ hardcode รายชื่อ

**Test:** `test_registry_rejects_duplicate_suffix`

#### 3.2 `carrier/detect.py` ☐

**ขึ้นกับ:** 3.1
**DoD**
- `sniff()` อ่าน 32 bytes แรก **จับคู่จาก magic ไม่ใช่นามสกุล**
- `.bmp` `.tif` `.webp` `.wav` `.mp3` `.avi` `.mp4` และไฟล์ทั่วไป → `UnsupportedCarrierError` พร้อมข้อความบอกตรงๆ
- ไฟล์ที่นามสกุลไม่ตรงเนื้อหา (เช่น `.png` ที่จริงเป็น JPEG) → ใช้เนื้อหาเป็นหลัก

**Test:** `test_unsupported_carrier_is_refused` · `test_extension_lying_uses_content`

#### 3.3 `carrier/image/jpeg.py` — **งานที่สำคัญที่สุดของโปรเจกต์** ☐

**ไฟล์:** `jpeg.py`, `_jpeg_codec.py`
**ขึ้นกับ:** 3.1
**DoD**
- เลือกไลบรารีแล้ว (`jpeglib` / `jpegio` / binding เอง) และ **ยืนยันว่าใช้ได้บน Windows**
- `planes()` คืน quantized DCT coefficient เป็น `int16` — **ห้าม dequantize ห้าม IDCT**
- `save()` Huffman-encode ใหม่เฉพาะข้อมูล coefficient · quant table / EXIF / marker อื่นคัดลอกดิบ
- `fingerprint()` = SHA-256(qtables ‖ w ‖ h ‖ subsampling ‖ n_components ‖ progressive)
- `nnz_ac()` คืนจำนวน non-zero AC ที่ตรงกับที่ใช้คำนวณ bpnzAC

> **★ Test แรกที่ต้องผ่านก่อนเขียนอย่างอื่นทั้งหมด**
> `test_jpeg_roundtrip_is_byte_exact` — `load()` แล้ว `save()` โดยไม่แก้ค่าใดเลย ต้องได้ไฟล์ที่เหมือนต้นฉบับทุก byte
> ถ้าข้อนี้ไม่ผ่าน ทุกอย่างที่สร้างต่อไม่มีความหมาย เพราะ double compression ทำให้ DCTR/GFR จับได้ตั้งแต่ยังไม่ได้ฝังอะไร

**Test:** `test_jpeg_roundtrip_is_byte_exact` (blocking) · `test_nnz_ac_matches_reference` · `test_progressive_jpeg_handled_or_refused`

#### 3.4 `carrier/image/png.py` ☐

**ไฟล์:** `png.py`, `png_metadata.py`
**ขึ้นกับ:** 3.1
**DoD**
- อ่าน/เขียน chunk ได้ ไม่ทำ CRC เสีย
- `planes()` คืน pixel array `uint8`
- `png_metadata.py` รับผิดชอบ iTXt / custom chunk (ย้ายมาจาก `metadata_handlers/png_handler.py` เดิม)
- ส่วนที่ไม่ได้แก้ต้อง byte-exact

**Test:** `test_png_roundtrip_is_byte_exact` · `test_crc_stays_valid`

#### 3.5 Fixtures ☐

**ไฟล์:** `tests/fixtures/` — jpg ที่ QF 50/75/95, png, ภาพ 64×64 และ 512×512
**ขึ้นกับ:** —
**DoD:** ครอบทุกกรณีที่ test ใน phase 3 ต้องใช้ · ขนาดรวมไม่เกิน 2 MB

---

### Phase 4 — Analyzer (นำโค้ดเดิมกลับ)

> **แหล่งที่มาของโค้ด:** ถ้ายังมีสำเนาของ `src/core/analyzer/**` จากเวอร์ชันก่อนย้ายโครง ให้นำกลับมาแล้วแก้ import — เสี่ยงต่ำและได้แอปที่ใช้งานได้เร็ว
> ถ้าไม่มีสำเนาแล้ว ให้เขียนใหม่ตาม DoD ของแต่ละ module ข้างล่าง — เนื้อหาอัลกอริทึมอยู่ใน `PROJECT_STRUCTURE.md` §4.8 ครบพอที่จะเขียนใหม่ได้

#### 4.1 External tools + docker bridge ☐

**ไฟล์:** `analyzer/external_tools/*.py` (6 ไฟล์), `analyzer/docker_bridge.py`
**ขึ้นกับ:** 2.1
**DoD:** wrapper ของ binwalk/exiftool/hachoir/mediainfo/pngcheck/zsteg ทำงานได้ · container build ได้

#### 4.2 Format handlers ☐

**ไฟล์:** `formats/base_handler.py`, `png_handler.py`, `wav_handler.py`, `avi_handler.py`
**ขึ้นกับ:** 4.1
**DoD:** `_entropy_reliable` ตั้งถูกต่อ format (PNG/JPEG ต้องเป็น `False` ไม่งั้น false positive) · overlay detection ใช้ `content_end` ที่ format ประกาศเอง

#### 4.3 Statistical modules ☐

**ไฟล์:** `modules/stat/*.py` (7 ไฟล์), `statistical_analyzer.py`, `structure_integrity.py`, `metadata_analyzer.py`
**ขึ้นกับ:** 4.2
**DoD:** chi-square · RS · WS · SPA · PDH · HCF-COM ให้ผลเหมือนก่อน refactor

#### 4.4 `formats/jpeg_handler.py` + `modules/dct/` — ของใหม่ ☐

**ไฟล์:** `jpeg_handler.py`, `modules/dct/double_compression.py`, `qtable_fingerprint.py`, `blockiness.py`
**ขึ้นกับ:** 3.3, 4.2
**DoD**
- ตรวจร่องรอย double compression จาก histogram ของ coefficient
- เทียบ quant table กับฐานข้อมูลกล้อง/ซอฟต์แวร์ แล้วบอกว่าน่าจะมาจากอะไร
- วัดความไม่ต่อเนื่องที่ขอบบล็อก 8×8

**Test:** `test_double_compression_detected_on_known_sample`

#### 4.5 Dispatcher + compare ☐

**ไฟล์:** `dispatcher.py`, `compare.py`
**ขึ้นกับ:** 4.2, 4.3
**DoD:** เลือก handler ตามชนิดไฟล์ · รวม report เป็นก้อนเดียว · เทียบ cover กับ stego ได้ทั้ง metadata/structure/statistics
**หนี้ที่ควรใช้คืนตอนนี้:** report เป็น `dict` ไม่มี schema ทำให้ GUI ต้องเดา key — เปลี่ยนเป็น dataclass

---

### Phase 5 — Coder (STC)

#### 5.1 `coder/base.py` + `stc.py` (numpy) ☐

**ขึ้นกับ:** 2.2
**DoD**
- `embed(values, rho_p1, rho_m1, bits, h)` คืน values ใหม่ · โยน `CapacityError` ที่แนบ `max_bits` และ `max_bpnzac` มาด้วย
- `extract(values, n_bits, h)` เป็นการคูณเมทริกซ์ เร็วกว่า embed ชัดเจน
- `H_HAT` ตรงกับตารางมาตรฐาน
- ตรวจ wet (`inf`) ถูกต้อง — ไม่แก้ตำแหน่งที่แก้ไม่ได้

**Test:** `tests/unit/test_coder.py` · `test_stc_roundtrip_all_rates` (0.05–0.4, h=10 และ 12) · `test_capacity_error_reports_max`

#### 5.2 `coder/_native/` — C kernel ☐

**ไฟล์:** `stc_kernel.c` (ตรวจของที่มี), `build.py`
**ขึ้นกับ:** 5.1
**DoD**
- ผลลัพธ์ **เหมือน numpy ทุก bit** ที่ทุก h และทุก seed
- build ได้บน Windows และ Linux · import fail แล้ว fallback ไป numpy พร้อม warning ที่ชัด
- เร็วกว่า numpy ≥ 20× ที่ h=10 บนภาพ 512×512

**Test:** `test_native_matches_numpy_bit_for_bit` · `test_fallback_warns_loudly`

#### 5.3 `coder/simulator.py` ☐

**ขึ้นกับ:** 5.1
**DoD:** `simulate_embedding()` คืนความน่าจะเป็นการเปลี่ยนแปลงต่อตำแหน่ง · `lambda_from_payload()` binary search หา λ ที่ทำให้ ternary entropy = target
**ใช้ทำอะไร:** แยก "ขีดจำกัดทางทฤษฎี" ออกจาก "ประสิทธิภาพของ STC จริง" ตอนรายงานผล

---

### Phase 6 — Cost Models

#### 6.1 `cost/base.py` + `wavelet.py` ☐

**ขึ้นกับ:** 2.2
**DoD:** `CostModel` ABC · `daubechies8_filters()` + `dwt2_directional()` ที่ juniward และ si_uniward ใช้ร่วมกัน

#### 6.2 `cost/juniward.py` ☐

**ขึ้นกับ:** 6.1, 3.3
**DoD**
- cost map ตรงกับ reference implementation ภายใน tolerance ที่บันทึกไว้
- wet position เป็น `inf` ไม่ใช่ตัวเลขใหญ่
- **ไม่ขึ้นกับ payload หรือคีย์เลย** (มี test ยืนยัน)

**Test:** `tests/unit/test_cost.py` · `test_juniward_matches_reference` · `test_cost_independent_of_payload`

#### 6.3 `cost/uerd.py` (baseline) ☐

**ขึ้นกับ:** 6.1
**DoD:** เร็วกว่า juniward ชัดเจน ใช้เป็น baseline ตอนวัดผล

#### 6.4 `cost/hill.py` (spatial) ☐

**ขึ้นกับ:** 6.1, 3.4
**DoD:** ใช้กับ PNG ได้ · cost map สมเหตุสมผล (ขอบภาพต่ำ พื้นเรียบสูง)

#### 6.5 `cost/si_uniward.py` ☐

**ขึ้นกับ:** 6.2
**DoD:** `requires_precover = True` · ถ้าไม่มี precover ต้องปฏิเสธชัดเจน ไม่ใช่ทำงานต่อแบบ degraded
**หมายเหตุ:** ทำหลังสายหลักเสร็จได้ ไม่บล็อกใคร

#### 6.6 `cost/legacy_texture.py` ☐

**ขึ้นกับ:** 6.1
**DoD:** gradient + local entropy ของ LSB-PP เดิม เก็บไว้เพื่อเทียบผลเท่านั้น

---

### Phase 7 — Crypto (P0 ต้องเสร็จก่อน)

> ทุก module ใน phase นี้ต้องมี KAT และห้าม merge ถ้าไม่มี test vector

#### 7.1 `crypto/kdf/` ☐

**ไฟล์:** `hkdf.py`, `labels.py`, `argon2.py`
**ขึ้นกับ:** 1.3, 2.1
**DoD:** `extract` / `expand` / `derive` ตรง RFC 5869 · `labels.py` รวม domain separation string ทั้งหมดไว้ที่เดียวพร้อมเลขเวอร์ชัน · argon2 ตาม RFC 9106 (t=3, m=64 MiB, p=4)
**Test:** KAT ของ HKDF-SHA256 ทุก vector

#### 7.2 `crypto/kem/` ☐

**ไฟล์:** `x25519.py`, `mlkem768.py`, `hybrid.py`
**ขึ้นกับ:** 7.1
**DoD**
- เลือกไลบรารี ML-KEM แล้ว (`cryptography` หรือ `liboqs-python`) — **ห้าม implement เอง**
- `hybrid` ใส่ `ss_x25519 ‖ ss_mlkem ‖ ct ‖ pk` เข้า IKM ครบ (ML-KEM ไม่ committing โดยตัวมันเอง)
**Test:** KAT ของ ML-KEM-768 · `test_hybrid_binds_ciphertext`

#### 7.3 `crypto/auth/` ☐

**ไฟล์:** `identity.py`, `transcript.py`, `key_binding.py`, `signatures.py`, `trust_store.py`
**ขึ้นกับ:** 1.2, 7.2
**DoD**
- `transcript.build()` มี length-prefix ทุกฟิลด์
- `AUTH_IMPLICIT` ทำงานได้และ overhead เป็น 0 byte จริง
- `AUTH_PQ_EXPLICIT` ใช้ Ed25519 + ML-DSA-65 — ต้องผ่านทั้งคู่จึงนับว่าถูก
- `TrustStore` บันทึกว่าเชื่อ identity นั้นเพราะอะไร (`fingerprint` / `qr` / `manual`) และ revoke ได้

**Test:** `test_mitm_key_substitution_is_rejected` · `test_transcript_canonicalization` · `test_revoked_identity_is_refused`

#### 7.4 `crypto/aead/gcm_siv.py` ☐

**ขึ้นกับ:** 7.1
**DoD:** `seal` / `open_` · **ทุกความล้มเหลวโยน `DecryptError` เดียว เวลาเท่ากัน**
**Test:** KAT ของ AES-256-GCM-SIV · `test_error_is_constant_time`

#### 7.5 `crypto/header.py` + `envelope.py` ☐

**ขึ้นกับ:** 1.3, 7.1
**DoD**
- header pack/unpack ตรง `FORMAT_SPEC.md` ทุก bit
- whitening ใช้ `K_hdr_session` ที่ derive จาก `ss` **ไม่ใช่จาก `MK[n]`**
- `choose_mode()` ตัดสินจากความจุจริง — ภาพ 512×512 ที่ 0.1 bpnzAC ต้องได้ `ENVELOPE_EXTERNAL` เสมอ

**Test:** `test_header_bits_are_indistinguishable_from_random` (monobit + runs test บน 10,000 header) · `test_envelope_mode_respects_capacity`

#### 7.6 `crypto/ratchet/` ☐

**ไฟล์:** `session.py`, `chain.py`, `state_store.py`, `state_lock.py`, `generation.py`, `rollback_guard.py`
**ขึ้นกับ:** 7.1, 7.2, 7.4
**DoD**
- `SendChain.next_message_keys()` zeroize `CK[n]` ทันทีหลัง derive `CK[n+1]`
- `MessageKeys` ครบ 4 ส่วน: `aead`, `nonce`, `hdr`, `seed_sel`
- `RecvChain` มี skipped pool ที่จำกัดขนาด + เพดาน ratchet ahead (กัน DoS จาก `ctr = 2²⁴−1`)
- lock ครอบทั้ง read-modify-write **ไม่ใช่แค่ตอนเขียน**
- commit ลำดับถูก: lock → load → verify generation → ratchet → เขียน state (temp→fsync→rename→fsync dir) → **แล้วจึงเขียน stego**
- `rollback_guard` มี docstring บอกตรงๆ ว่าตรวจจับได้ ไม่ได้ป้องกัน

**Test:** `test_state_rollback_is_detected` · `test_two_processes_cannot_use_same_counter` · `test_crash_during_commit_never_reuses_counter` · `test_ratchet_limit_enforced`

#### 7.7 `crypto/keystore.py` + `zeroize.py` + `lifecycle/` ☐

**ขึ้นกับ:** 7.1
**DoD**
- private key wrap ด้วย Argon2id + AEAD เสมอ ไม่มีทางเก็บแบบดิบ
- `zeroize()` มี docstring ประกาศข้อจำกัดของ Python ตรงๆ
- `KeyState` state machine — ใช้คีย์ที่ `REVOKED`/`DESTROYED` ต้องโยน error
- `destroy_session()` คืน report ว่าลบอะไรไปบ้าง

---

### Phase 8 — Pipeline + Engines

#### 8.1 `pipeline/context.py` + `registry.py` ☐

**ขึ้นกับ:** 2.1
**DoD:** `RunContext(progress, logger, cancel_token)` · `EngineRegistry.resolve()` โยน `IncompatibleEngineError` ถ้า engine ใช้กับ domain นั้นไม่ได้ · `for_domain()` ให้ UI สร้าง dropdown

#### 8.2 `pipeline/engines/base.py` ☐

**ขึ้นกับ:** 8.1
**DoD:** `Engine` ABC · `EmbedRequest` / `EmbedResult` / `ExtractRequest` / `ExtractResult` เป็น dataclass

#### 8.3 `pipeline/engines/juniward_stc.py` — engine หลัก ☐

**ขึ้นกับ:** 3.3, 5.1, 6.2, 7.6, 8.2
**DoD:** ประกอบชั้นล่างตามลำดับใน `PROJECT_STRUCTURE.md` §2.3 · **ไม่มี math ใหม่ในไฟล์นี้** · AAD = header ‖ `carrier.fingerprint()`
**Test:** `tests/integration/test_stc_engine.py` · `test_ciphertext_from_other_carrier_is_rejected`

#### 8.4 `pipeline/engines/hill_stc.py` ☐

**ขึ้นกับ:** 3.4, 5.1, 6.4, 7.6, 8.2
**DoD:** เหมือน 8.3 แต่ spatial domain

#### 8.5 `pipeline/embed.py` + `extract.py` ☐

**ขึ้นกับ:** 8.3
**DoD**
- ลำดับตรงตาม §2.3 / §2.4
- **เซฟ ratchet state ก่อนเขียนไฟล์ stego เสมอ** (ยอมข้าม counter ดีกว่าใช้ซ้ำ)
- extract ถอด header ได้ก่อนรู้ `ctr` (ใช้ `K_hdr_session`)

**Test:** `test_embed_extract_roundtrip` ทุก payload rate · `test_state_saved_before_output_written`

#### 8.6 `pipeline/engines/lsbpp.py` + `locomotive.py` + `metadata.py` ☐

**ขึ้นกับ:** 8.2, 3.4
**DoD:** นำโค้ดเดิมกลับแล้วห่อให้เข้า `Engine` interface · `supported_domains = ("dct", "spatial")` เท่านั้น · `metadata` ตัดส่วน MP3 ID3 ออก

#### 8.7 `pipeline/yaml/` ☐

**ไฟล์:** `schema.py`, `loader.py`, `validate.py` + แก้ template
**ขึ้นกับ:** 8.1, 8.5
**DoD**
- `schema` แยกจาก `validate` แยกจากการรัน (โค้ดเดิมรวมทุกอย่างใน `config_mode.py`)
- ตรวจ reference เป็นวงจร · index เกินจำนวน output · engine ไม่รองรับ domain ของ cover
- **แก้ template 5 ไฟล์:** ตัดอันที่อ้าง mp3 (`02_nested_mp3_carrier`, `04_crossmedia_key_split`) หรือเปลี่ยนเป็น jpg/png

**Test:** `tests/integration/` — template ทุกไฟล์ต้องรันผ่าน

#### 8.8 `ui/cli/` ☐

**ขึ้นกับ:** 8.5
**DoD:** `sieng embed` / `extract` / `analyze` / `compare` / `pipeline run` ทำงานได้ · argparse → typer

---

### Phase 9 — UI

> **แหล่งที่มาของโค้ด:** ถ้ายังมีสำเนาของ `src/gui/**` จากเวอร์ชันก่อนย้ายโครง ให้นำกลับมาแล้วต่อสายเข้า pipeline ใหม่
> ถ้าไม่มีสำเนาแล้ว ต้องเขียน GUI ใหม่ — ประเมินงานใหม่ก่อนเริ่ม เพราะส่วนนี้เดิมมีขนาดราว 11,000 บรรทัด · `assets/` และ `default.qss` ยังอยู่ครบ ใช้ต่อได้ทันที

#### 9.1 Shell + components ☐

**ไฟล์:** `main_window.py`, `components/*.py` (14 ไฟล์)
**ขึ้นกับ:** 0.3
**DoD:** window + sidebar + page router ทำงาน · `worker.py` กันงานหนักออกจาก UI thread

#### 9.2 Pages ☐

**ไฟล์:** `pages/*.py` + `sub_pages/**`
**ขึ้นกับ:** 9.1, 8.5, 4.5
**DoD**
- 4 หน้าเดิมทำงานได้: embed / extract / analyzer / compare
- **หน้า embed แสดงนามสกุลที่รองรับ = jpg/png · หน้า analyze แสดง jpg/png/wav/avi** และผู้ใช้เห็นความต่างชัด
- dropdown ของ engine มาจาก `registry.for_domain()` ไม่ hardcode

#### 9.3 Tabs ☐

**ไฟล์:** `tabs/**`
**ขึ้นกับ:** 9.2
**DoD:** tab ของ analyzer / compare กลับมาครบ · tab ของ embed สร้าง form จาก schema ของ engine (เพิ่ม engine แล้วไม่ต้องเขียน tab ใหม่)
**หนี้ที่ควรใช้คืน:** `assets/png/` ซ้ำกับ `assets/svg/` เกือบทั้งหมด — เหลือ svg อย่างเดียว

#### 9.4 หน้าจัดการ identity — ของใหม่ ☐

**ขึ้นกับ:** 7.3, 9.1
**DoD**
- สร้าง / นำเข้า / ส่งออก identity ได้
- **บังคับให้ผู้ใช้เทียบ fingerprint ก่อนเชื่อ** — ต้องไม่ใช่ dialog ที่กด "ตกลง" ผ่านได้
- แสดง revocation status ชัดเจน

---

### Phase 10 — Research Evaluation

#### 10.1 Datasets ☐

**ไฟล์:** `datasets/bossbase.py`, `alaska2.py`, `split.py` (มีแล้ว), `quality.py`, `source_meta.py`
**ขึ้นกับ:** 3.3
**DoD:** verify hash ของ dataset · `paired_split()` การันตีว่า cover/stego ของภาพเดียวกันอยู่ฝั่งเดียวกัน · สร้างชุด QF 50–95 จากต้นฉบับเดียวกันได้
**Test:** `test_paired_split_never_leaks_same_image`

#### 10.2 Feature extractors ☐

**ไฟล์:** `features/dctr.py`, `gfr.py`, `models/ensemble.py`
**ขึ้นกับ:** 3.3
**DoD:** DCTR 8,000 มิติ · GFR 17,000 มิติ · FLD ensemble ให้ผลใกล้เคียงค่าที่รายงานในเปเปอร์บน dataset เดียวกัน

#### 10.3 SRNet ☐

**ไฟล์:** `models/srnet/model.py`, `train.py`
**ขึ้นกับ:** 10.1
**DoD:** เทรนได้ · curriculum จาก payload สูงไปต่ำ · **`torch` อยู่ใน `research/` เท่านั้น**

#### 10.4 Experiments + stats ☐

**ไฟล์:** `experiments/*.yaml` (4 ไฟล์), `stats.py` (มีแล้ว), `metrics.py`
**ขึ้นกับ:** 10.2, 10.3, 8.3
**DoD**
- 4 มิติครบ: payload sweep · quality sweep · cross-dataset · cover-source mismatch
- **ทุกผลรายงานเป็น `P_E` + 95% CI + N + seed + เวอร์ชันของโค้ด + dataset hash** — ห้ามรายงานตัวเลขเปล่า
- บันทึกผลเป็น CSV ที่อ่านซ้ำได้

---

### Phase 11 — Hardening & Release

#### 11.1 Analyzer sandbox ☐

**ไฟล์:** `analyzer/sandbox.py`, `resource_policy.py`, `limits.py`, `timeout.py`
**ขึ้นกับ:** 4.1
**DoD**
- container control ครบ 10 ข้อตาม §4.8 (network none · read-only · memory · cpus · pids · cap-drop · no-new-privileges · user nobody · timeout · ไม่ mount docker socket)
- input limit 6 ข้อเช็กก่อนถึง parser (ขนาดไฟล์ · megapixel · อัตราขยาย · ความลึก container · EXIF entry · JPEG marker)

**Test:** `test_bomb_rejected` · `test_malformed_input_contained`

#### 11.2 Fuzzing ☐

**ไฟล์:** `tests/fuzz/fuzz_{jpeg,header,envelope,stc,pipeline,state}.py` + `corpus/`
**ขึ้นกับ:** 3.3, 7.5, 5.1, 8.7, 7.6
**DoD**
- 6 target รันได้ · ≥ 1 ชม./target ต่อ release โดยไม่มี crash/hang/memory ระเบิด/secret รั่ว
- crash ทุกตัวเข้า corpus เป็น regression ถาวร
- **บันทึก known gap:** atheris เข้าถึงแค่ชั้น Python — memory bug ใน libjpeg ต้องใช้ libFuzzer ระดับ C (Phase 2)

#### 11.3 Supply chain ☐

**ขึ้นกับ:** 0.2
**ไฟล์:** เพิ่ม session ใน `noxfile.py`
**DoD**
- `nox -s deps` รัน `pip-audit` เทียบ CVE — fail ที่ระดับ high ขึ้นไป
- `nox -s sbom` สร้าง SBOM ด้วย `cyclonedx-bom` ลง `dist/sbom.cyclonedx.json`
- `nox -s sast` รัน `bandit` + `semgrep`
- `nox -s secrets` รัน `detect-secrets` บนไฟล์ทั้งโปรเจกต์ (กันคีย์จริงหลุดปนไปกับซอร์ส)
- `nox -s image-scan` รัน `trivy` บน image ของ analyzer — ต้องมี Docker
- **ทั้งหมดรันในเครื่อง** ไม่พึ่ง hosted service · ผลลัพธ์เก็บเป็นไฟล์ใน `dist/` เพื่อแนบไปกับ release

#### 11.4 Security matrix + release ☐

**ไฟล์:** `docs/SECURITY_MATRIX.md`, `docs/KEY_LIFECYCLE.md`, `scripts/release.py`
**ขึ้นกับ:** ทั้งหมด
**DoD**
- ตาราง 20 threat ใน §11.2 เติมช่อง Status ครบทุกแถว
- `MANIFEST.json` ครบ: version · SHA-256 ของ source archive · SHA-256 ของ artifact · SBOM · lock hash · dataset version · experiment config · **`known_gaps`**
- ตัดสินใจเรื่อง license แล้ว

---

## 5. ตารางติดตามความคืบหน้า

| Phase | Module | Status |
|:---:|---|:---:|
| 0 | 0.1 Packaging · 0.2 Tooling & local checks · 0.3 Entry point | ☑ ☑ ☑ |
| 1 | 1.1 THREAT_MODEL · 1.2 SESSION_PROTOCOL · 1.3 FORMAT_SPEC | ☑ ☑ ☑ |
| 2 | 2.1 common · 2.2 domain | ☑ ☑ |
| 3 | 3.1 base · 3.2 detect · 3.3 jpeg · 3.4 png · 3.5 fixtures | ☑ ☑ ☑ ☑ ☑ |
| 4 | 4.1 tools · 4.2 formats · 4.3 stat · 4.4 dct · 4.5 dispatcher | ☐ ☐ ☐ ☐ ☐ |
| 5 | 5.1 stc · 5.2 native · 5.3 simulator | ☐ ☐ ☐ |
| 6 | 6.1 base · 6.2 juniward · 6.3 uerd · 6.4 hill · 6.5 si · 6.6 legacy | ☐ ☐ ☐ ☐ ☐ ☐ |
| 7 | 7.1 kdf · 7.2 kem · 7.3 auth · 7.4 aead · 7.5 header · 7.6 ratchet · 7.7 keystore | ☐ ☐ ☐ ☐ ☐ ☐ ☐ |
| 8 | 8.1 context · 8.2 engine base · 8.3 juniward-stc · 8.4 hill-stc · 8.5 embed/extract · 8.6 legacy engines · 8.7 yaml · 8.8 cli | ☐ ☐ ☐ ☐ ☐ ☐ ☐ ☐ |
| 9 | 9.1 shell · 9.2 pages · 9.3 tabs · 9.4 identity | ☐ ☐ ☐ ☐ |
| 10 | 10.1 datasets · 10.2 features · 10.3 srnet · 10.4 experiments | ☐ ☐ ☐ ☐ |
| 11 | 11.1 sandbox · 11.2 fuzz · 11.3 supply chain · 11.4 release | ☐ ☐ ☐ ☐ |

**Blocking chain ที่ต้องจำ:** `1.3 FORMAT_SPEC` → `7.5 header` → `8.5 embed` · `3.3 jpeg byte-exact` → ทุกอย่างที่เกี่ยวกับ JPEG

---

## 6. เรื่องที่ยังไม่ได้ตัดสินใจ

ต้องเคาะก่อนถึง phase ที่ระบุ ไม่งั้นจะติด

| # | เรื่อง | ทางเลือก | ต้องเคาะก่อน |
|:--:|---|---|:---:|
| ~~D1~~ | ~~ไลบรารี JPEG DCT~~ | **เคาะแล้ว: `jpeglib` 1.0.2 + libjpeg 6b** — spike ยืนยันว่า entropy data เหมือนเดิมทุก byte · ต่างแค่ header 3 จุด (APP0 ซ้ำ · component id ใน SOF/SOS) จึงประกอบไฟล์เองจาก header เดิม | ✔ |
| D2 | ไลบรารี ML-KEM-768 | `cryptography` (ถ้ารองรับ) · `liboqs-python` — **ห้ามเขียนเอง** | Phase 7.2 |
| D3 | ไลบรารี ML-DSA-65 | `liboqs-python` · ตัด `AUTH_PQ_EXPLICIT` ออกจาก Phase 1 | Phase 7.3 |
| ~~D4~~ | ~~Python เวอร์ชันต่ำสุด~~ | **เคาะแล้ว: 3.11+** — ตั้งไว้ใน `pyproject.toml` แล้ว | ✔ |
| D5 | STC kernel | C + numpy fallback · numpy อย่างเดียวไปก่อน | Phase 5.2 |
| ~~D6~~ | ~~ขนาด header~~ | **เคาะแล้ว: 12 B** — binding tag ซ้ำซ้อนกับ AAD (`FORMAT_SPEC.md` §3.1) | ✔ |
| ~~D7~~ | ~~`tests/` 13 ไฟล์ที่มีอยู่~~ | **เคาะแล้ว: ลบทิ้ง** — เหลือโครงโฟลเดอร์ 6 ชั้น เขียน test ใหม่ตอนทำแต่ละ module | ✔ |
| ~~D8~~ | ~~`src/sieng/_deferred/`~~ | **เคาะแล้ว: ลบทิ้ง** | ✔ |
| D9 | Template yaml 2 ไฟล์ที่อ้าง mp3 | เปลี่ยนเป็น jpg/png · ย้ายออกไปรอ Phase 2 | Phase 8.7 |
| D10 | assets png ซ้ำ svg 38 ไฟล์ | ลบ png · เก็บทั้งคู่ | Phase 9.3 |
| D11 | License | MIT · Apache-2.0 · ไม่เผยแพร่ | Phase 11.4 |
| D12 | แจก binary หรือให้ build เอง | เครื่องมือ steganography ที่แจก binary มักโดน antivirus flag | Phase 11.4 |

---

## 7. เริ่มงานครั้งถัดไปที่ไหน

1. **ปิด Phase 0.2 ให้จบ** — รัน `pip install -e ".[gui,analyzer,dev]"` บนเครื่องจริง แล้ว `nox`
   ต้องผ่านครบ · แก้สิ่งที่แดง · สร้าง lockfile
   (ยังเหลือข้อนี้เพราะเครื่องที่ใช้สร้างไฟล์เข้า PyPI ไม่ได้ จึงยังไม่ได้รัน ruff/mypy/nox จริง)
2. **Phase 5** (`coder/stc.py`) — ขึ้นกับ `domain` อย่างเดียว เป็นตัวถัดไปในสายหลัก
3. **Phase 6** (`cost/`) ต่อจาก 5 แล้ว Phase 8 จะประกอบทั้งหมดเข้าด้วยกันได้
4. เคาะ **D2/D3** (ไลบรารี ML-KEM/ML-DSA) ก่อนถึง Phase 7 · **D5** (STC เป็น C หรือ numpy) ก่อน Phase 5.2

> **ก่อนเริ่มเขียนโค้ดจริง แนะนำให้คัดลอกโฟลเดอร์ทั้งชุดเก็บไว้เป็นจุดย้อนกลับ** — โปรเจกต์นี้ไม่มีระบบกู้คืนอัตโนมัติ งานที่หายไปแล้วหายเลย
