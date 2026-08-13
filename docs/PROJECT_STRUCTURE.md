# SIENG3 — Project Structure Overview

> เอกสารอ้างอิงโครงสร้างโปรเจกต์ฉบับสมบูรณ์
> เป้าหมาย: developer ที่เพิ่งเข้าทีมอ่านเอกสารนี้จบแล้วรู้ว่าโค้ดอยู่ตรงไหน ทำอะไร คุยกับใคร และถ้าจะเพิ่มของใหม่ต้องแตะไฟล์ไหน โดยไม่ต้องเปิดอ่านทีละไฟล์
> เวอร์ชันเอกสาร: **1.2** · อ้างอิง `docs/ARCHITECTURE_v3.md`

**สิ่งที่เปลี่ยนใน 1.2 — ลดสโคป carrier**

Phase 1 ฝังได้เฉพาะ **`.jpg` และ `.png`** เท่านั้น · carrier อื่นทั้งหมดเลื่อนไป Phase 2 (`bmp` `tiff` `webp` `wav` `mp3` `avi` `mp4` `blob`)
`analyzer/` **ไม่ถูกลดสโคป** — ยังตรวจ wav/avi ได้ตามเดิม เพราะเป็นคนละหน้าที่กัน (ดู §1.6 และท้ายตาราง §4.8)
รายละเอียดเหตุผลอยู่ใน §4.2 · แผนเปิดสโคปกลับอยู่ใน §12.3

**สิ่งที่เปลี่ยนใน 1.1** — รวมผลจาก Senior Cyber Security Architecture Review (verdict: *approve with conditions*)

| เพิ่ม | ระดับ | อยู่ที่ |
|---|:---:|---|
| Threat model + แยกคำศัพท์ FS / PCS / key compromise | **P0** | §2.6 |
| Authentication / key binding (`crypto/auth/`) | **P0** | §2.7, §4.6 |
| Session envelope + **การคำนวณความจุจริงที่บังคับการตัดสินใจ** | **P0** | §2.7.2–2.7.3, §7.4 |
| Anti-rollback / concurrent state protection | **P0** | §2.8, §4.6 |
| Parser resource limits + sandbox hardening | P1 | §4.8 |
| Fuzzing harness | P1 | §4.12 |
| Key lifecycle (`crypto/lifecycle/`) | P1 | §4.6 |
| Security evaluation matrix (20 threat) | P1 | §11 |
| Cross-quality / cross-dataset / CSM / confidence interval | P1 | §4.11 |
| SBOM + dependency scan + SAST + secret scan | P1 | §9.3 |
| Reproducible release manifest | P2 | §9.5 |
| Re-KEM / PCS, OS-level counter, C-level fuzzing | P2 | §12.3 |

**ข้อค้นพบที่เปลี่ยนการออกแบบ:** session bootstrap แบบลงนาม PQ เต็มรูปมีขนาด ≈ 6.5 KB ขณะที่ภาพ 512×512 QF75 ที่ 0.4 bpnzAC จุได้เพียง ≈ 1.3 KB — **ต่างกัน 5 เท่า** การเลือกรูปแบบ envelope จึงถูกบังคับด้วยความจุ ไม่ใช่ความชอบ และการพิสูจน์ตัวตนต้องใช้วิธีที่ overhead เป็นศูนย์เป็นค่าเริ่มต้น (ดู §2.7)

---

## 0. วิธีอ่านเอกสารนี้

### 0.1 Status legend

ทุกไฟล์และทุกโมดูลในเอกสารนี้จะมีรหัสสถานะกำกับ เพื่อให้แยกออกว่าอะไรมีอยู่แล้วและอะไรยังต้องเขียน

| รหัส | ความหมาย | สิ่งที่ต้องทำ |
|:---:|---|---|
| `E` | **Existing** — มีโค้ดอยู่แล้วในโปรเจกต์ปัจจุบัน ย้ายตำแหน่งอย่างเดียว | ย้ายไฟล์ + แก้ import path |
| `R` | **Refactor** — มีโค้ดอยู่แล้ว แต่ต้องผ่าตัดให้เข้ากับ interface ใหม่ | แยกความรับผิดชอบ ตัด coupling |
| `N` | **New** — ยังไม่มี ต้องเขียนใหม่ทั้งหมด | เขียนตั้งแต่ต้น + test |
| `N!` | **New, security-critical** — เขียนใหม่และต้องผ่าน security review + KAT | ห้าม merge ถ้าไม่มี test vector |
| `—` | **Deferred** — วางที่ไว้แล้วแต่เลื่อนไป Phase 2 โดยเจตนา | ยังไม่ต้องทำ แต่ห้ามลืม |

เครื่องหมาย `★` หมายถึงจุดที่พลาดแล้วกระทบความปลอดภัยทั้งระบบ · `P0`/`P1`/`P2` คือลำดับความสำคัญตาม §12

### 0.2 คำเตือนก่อนเริ่มอ่าน

เอกสารนี้อธิบาย **โครงเป้าหมาย (target structure)** ไม่ใช่สภาพปัจจุบันของโฟลเดอร์
ถ้าคุณเปิดโฟลเดอร์ตอนนี้แล้วไม่เจอไฟล์ที่เขียนไว้ ให้ดูรหัสสถานะ — `N` แปลว่ายังไม่มีจริง ตารางแมป "ไฟล์เก่า → ไฟล์ใหม่" อยู่ในหัวข้อ 10

---

## 1. Project Overview

### 1.1 ข้อมูลโปรเจกต์

| หัวข้อ | รายละเอียด |
|---|---|
| **Project Name** | SIENG3 (Steganography Integrated ENGine, generation 3) |
| **Codename เดิม** | SIENG2_2 |
| **Project Type** | Desktop application + CLI + research framework |
| **Domain** | Information hiding / Steganography & Steganalysis / Applied cryptography |
| **Project Purpose** | เครื่องมือสำหรับ **ฝัง** ข้อมูลลับลงในไฟล์สื่อโดยตรวจจับได้ยากที่สุดเท่าที่วิธีการปัจจุบันทำได้ **ถอด** ข้อมูลกลับ และ **ตรวจสอบ** ไฟล์ต้องสงสัยว่ามีข้อมูลซ่อนอยู่หรือไม่ พร้อมกรอบการวัดผลเชิงวิชาการที่ทำซ้ำได้ |
| **Primary User** | นักวิจัยด้าน steganography, นักศึกษาที่ทำวิทยานิพนธ์สาขานี้, security analyst ที่ต้องตรวจไฟล์ต้องสงสัย |
| **License** | ยังไม่กำหนด — ต้องตัดสินใจก่อนเผยแพร่ (ดูหัวข้อ 9.4) |

### 1.2 Problem ที่ระบบต้องการแก้ไข

| # | ปัญหา | ผลกระทบถ้าไม่แก้ | สิ่งที่ SIENG3 ทำ |
|:---:|---|---|---|
| P1 | เครื่องมือ steganography ทั่วไปใช้ **LSB ธรรมดา** ซึ่ง detector สมัยใหม่ (DCTR, SRNet) ตรวจเจอเกือบ 100% ที่ payload ต่ำมาก | ข้อมูลที่คิดว่าซ่อนแล้ว จริงๆ ตรวจเจอได้ทันที | ใช้ **adaptive distortion (J-UNIWARD) + STC** ซึ่งเป็นมาตรฐานงานวิจัยปัจจุบัน |
| P2 | เครื่องมือส่วนใหญ่รองรับเฉพาะ **ภาพ lossless** (PNG/BMP) ทั้งที่ไฟล์ที่คนส่งกันจริงในโลกคือ **JPEG** | ใช้งานจริงไม่ได้ เพราะการส่ง PNG จำนวนมากเป็นพฤติกรรมผิดปกติในตัวมันเอง | รองรับ JPEG ที่ระดับ **quantized DCT coefficient** โดยไม่บีบอัดซ้ำ |
| P3 | **Payload ที่ฝังมี magic string เป็น plaintext** (`b"SES"` ในโค้ดเดิม) | ผู้ตรวจที่เดา embedding path ถูก ยืนยันได้ทันทีว่ามีข้อมูลซ่อน — undetectability พังทั้งระบบ | header ถูก **whiten ด้วย keystream** ทุก bit ที่ฝังเป็นค่าสุ่มสม่ำเสมอ |
| P4 | ระบบเดิมใช้ **RSA-3072** ซึ่งจะถูก quantum computer ทำลายในอนาคต และข้อมูลที่ถูกดักเก็บวันนี้จะถูกถอดในภายหลัง (harvest now, decrypt later) | ความลับระยะยาวไม่ปลอดภัย | **hybrid PQC**: X25519 + ML-KEM-768 ต้องแตกทั้งคู่จึงจะถอดได้ |
| P5 | ใช้ **คีย์เดียวตลอด session** — คีย์หลุดครั้งเดียว ข้อมูลเก่าทั้งหมดหลุดตาม | ไม่มี forward secrecy | **symmetric ratchet** คีย์ใหม่ต่อหนึ่งไฟล์ ลบคีย์เก่าทิ้ง |
| P6 | **เพิ่ม format หรือ algorithm ใหม่ต้องแก้ orchestrator** (`config_mode.py` ใช้ if/elif) | โค้ดเปราะ เพิ่มของทีต้องแก้หลายจุด เสี่ยง regression | **plugin registry** เพิ่ม format = เพิ่ม 1 ไฟล์ ไม่แตะโค้ดเดิม |
| P7 | ไม่มีกรอบวัดผลที่เป็นมาตรฐาน | เคลมว่า "ปลอดภัย" โดยไม่มีตัวเลขรองรับ | `research/` วัดด้วย DCTR + GFR + SRNet บน BOSSbase + ALASKA2 รายงานเป็น P_E |

### 1.3 Main Features

| กลุ่ม | Feature | คำอธิบาย | Status |
|---|---|---|:---:|
| **Embed** | JPEG adaptive embedding | J-UNIWARD + STC บน quantized DCT | `N` |
| | Side-informed embedding | SI-UNIWARD เมื่อมีภาพต้นฉบับก่อนบีบอัด | `N` |
| | Spatial embedding | HILL + STC สำหรับ PNG | `N` |
| | Legacy LSB-PP | LSB adaptive เดิม เก็บไว้เพื่อเปรียบเทียบ | `R` |
| | Locomotive | ฝังกระจายหลายไฟล์แบบต่อโซ่ — **เฉพาะ jpg/png** | `R` |
| | Metadata embedding | PNG iTXt / JPEG APPn — **ตัด MP3 ID3 ออก** | `R` |
| | Configurable pipeline | ต่อหลาย engine เป็นสายงานผ่าน YAML | `R` |
| **Crypto** | Hybrid PQC KEM | X25519 + ML-KEM-768 | `N!` |
| | **Identity authentication** | Ed25519 + ML-DSA-65 ลงนาม prekey bundle — **กัน MITM** | `N!` |
| | **Transcript binding** | ผูก identity + pk + ct + suite + sid เข้า session key | `N!` |
| | **Session envelope** | กำหนดตำแหน่งของ KEM ciphertext อย่างเป็นทางการ | `N!` |
| | Symmetric ratchet | คีย์ใหม่ต่อข้อความ + forward secrecy | `N!` |
| | **Anti-rollback state** | monotonic generation + exclusive lock + crash-safe commit | `N!` |
| | **Key lifecycle** | generate → store → load → use → rotate → revoke → destroy | `N!` |
| | AEAD | AES-256-GCM-SIV, AAD ผูกกับ carrier | `N!` |
| | Password mode | Argon2id KDF สำหรับโหมดรหัสผ่าน | `R` |
| | Re-KEM / PCS *(Phase 2)* | รีเซ็ต chain ด้วยความลับใหม่เป็นระยะ | `N` |
| **Hardening** | Analyzer resource limits | CPU / RAM / PID / timeout / quota ของ sandbox | `N` |
| | Fuzzing harness | JPEG, header, STC, YAML, state store | `N` |
| | Supply chain controls | SBOM + dependency scan + SAST + secret scan | `N` |
| **Extract** | Auto-detect + extract | ถอดกลับรวมทั้ง pipeline หลายชั้น | `R` |
| **Analyze** | Structural analysis | binwalk, hachoir, overlay, chunk integrity | `E` |
| | Statistical attacks | Chi-square, RS, WS, SPA, PDH, HCF-COM | `E` |
| | DCT analysis | double compression, qtable fingerprint | `N` |
| | Metadata analysis | exiftool + heuristic | `E` |
| | Compare mode | เทียบ cover กับ stego แบบ side-by-side | `E` |
| **Research** | Feature extractors | DCTR, GFR | `N` |
| | Deep detector | SRNet | `N` |
| | Payload sweep | 0.05 / 0.1 / 0.2 / 0.4 bpnzAC | `N` |

### 1.4 Technology Stack

#### Programming Languages

| ภาษา | ใช้ทำอะไร | สัดส่วนโดยประมาณ |
|---|---|:---:|
| Python 3.11+ | ทั้งระบบ: core, GUI, CLI, research | ~92% |
| C / Cython | STC Viterbi kernel (`coder/_native/`) — Python ช้าเกินใช้งานจริง | ~5% |
| QSS (Qt Style Sheets) | ธีมของ GUI | ~2% |
| PowerShell / Shell | build script ของ Docker | ~1% |

#### Frameworks / Libraries

| Package | เวอร์ชัน | หน้าที่ | ชั้นที่ใช้ | Status |
|---|---|---|---|:---:|
| `PyQt6` | 6.11.x | GUI framework ทั้งหมด | `ui/gui` | `E` |
| `numpy` | 2.4.x | array ทุกอย่าง: coefficient, cost map, mask | `domain`, `cost`, `coder` | `E` |
| `scipy` | 1.17.x | convolution ของ wavelet filter bank | `cost` | `E` |
| `pillow` | 12.x | อ่าน/เขียนภาพ spatial | `carrier/image` | `E` |
| `opencv-python` | 4.13.x | Sobel gradient, image ops ของ LSB-PP | `cost/hill`, legacy | `E` |
| `scikit-image` | 0.26.x | local entropy ของ LSB-PP | legacy | `E` |
| `cryptography` | 47.x | X25519, HKDF-SHA256, AES-GCM-SIV, Argon2id | `crypto` | `E` |
| **`jpeglib`** *(หรือ `jpegio`)* | TBD | **อ่าน/เขียน quantized DCT coefficient ตรง** | `carrier/image/jpeg` | `N` |
| **`liboqs-python`** *(ถ้าจำเป็น)* | TBD | ML-KEM-768 — ใช้ต่อเมื่อ `cryptography` ยังไม่รองรับ | `crypto/kem` | `N` |
| **`liboqs-python`** | TBD | **ML-DSA-65** (FIPS 204) สำหรับ identity signature ฝั่ง PQ | `crypto/auth` | `N` |
| `portalocker` *(หรือ `filelock`)* | TBD | exclusive lock ของ ratchet state ข้าม process/OS | `crypto/ratchet` | `N` |
| `atheris` | TBD | coverage-guided fuzzing ฝั่ง Python | `tests/fuzz` | `N` |
| `pip-audit` + `cyclonedx-bom` | TBD | dependency vulnerability scan + SBOM | CI | `N` |
| `bandit` + `semgrep` | TBD | SAST | CI | `N` |
| `trivy` *(หรือ `grype`)* | TBD | สแกน container image | CI | `N` |
| ~~`mutagen`~~ | 1.48.x | ID3 tag ของ MP3 — **ถอดออกจาก Phase 1** พร้อม carrier เสียง | — | `—` |
| `PyExifTool` | 0.5.x | wrapper ของ exiftool | `analyzer/external_tools` | `E` |
| `hachoir` | 3.3.x | แยกโครงสร้างไฟล์ | `analyzer/external_tools` | `E` |
| `PyYAML` | 6.x | pipeline config | `pipeline/yaml` | `E` |
| `networkx` | 3.6.x | กราฟ dependency ของ pipeline | `pipeline` | `E` |
| `cffi` | 2.x | binding ของ STC native kernel | `coder/_native` | `E` |
| `torch` | TBD | SRNet — **อยู่ใน research เท่านั้น** | `research/models` | `N` |
| `pytest` + `hypothesis` | TBD | unit + property-based test | `tests/` | `N` |

> **กฎเหล็กเรื่อง dependency:** `torch` ห้ามปรากฏใน `src/sieng/` เด็ดขาด ถ้า GUI ต้อง import torch แปลว่ามีคนวางโค้ดผิดชั้น การติดตั้งฝั่ง product ต้องเบาพอที่จะรันบนเครื่องธรรมดาได้

#### Database

| หัวข้อ | รายละเอียด |
|---|---|
| **DBMS** | ไม่มี — โปรเจกต์นี้เป็น file-based ทั้งหมดโดยเจตนา |
| **เหตุผล** | ข้อมูลลับไม่ควรถูกเก็บใน DB ที่มี WAL, temp file, และ backup ที่ควบคุมไม่ได้ ทุกอย่างเป็นไฟล์ที่ผู้ใช้ควบคุมและลบเองได้ |
| **State ที่ต้อง persist** | `crypto/ratchet/state_store.py` — เก็บ chain key + counter เป็นไฟล์เข้ารหัสด้วย AEAD เขียนแบบ atomic (write temp → fsync → rename) |
| **Config** | YAML (`pipeline/yaml/`) และ TOML (`pyproject.toml`) |
| **ผลการทดลอง** | CSV / Parquet ใน `research/results/` — ไม่ใช่ข้อมูลลับ |

#### External Services

| Service | ประเภท | ใช้ทำอะไร | Runtime | Status |
|---|---|---|---|:---:|
| **exiftool** | CLI binary | อ่าน metadata ทุก format | Docker container | `E` |
| **binwalk** | CLI binary | หา signature ของไฟล์ฝังใน + entropy scan | Docker container | `E` |
| **zsteg** | Ruby gem | ตรวจ LSB ใน PNG/BMP | Docker container | `E` |
| **pngcheck** | CLI binary | ตรวจ CRC ของ PNG chunk | Docker container | `E` |
| **mediainfo** | CLI binary | สรุป stream ของไฟล์เสียง/วิดีโอ | Docker container | `E` |
| **BOSSbase 1.01** | Dataset | 10,000 ภาพ grayscale 512×512 มาตรฐานงานวิจัย | ดาวน์โหลดครั้งเดียว | `N` |
| **ALASKA2** | Dataset | 75,000 ภาพสีจาก Kaggle ใกล้เคียงภาพจริง | ดาวน์โหลดครั้งเดียว | `N` |

> **ไม่มี network call ตอน runtime** — ระบบนี้ทำงาน offline ได้ 100% ตามเจตนา เครื่องมือภายนอกทั้งหมดรันในเครื่อง (ผ่าน Docker) ไม่มีการส่งไฟล์ผู้ใช้ออกนอกเครื่องในทุกกรณี

#### Runtime Environment

| หัวข้อ | รายละเอียด |
|---|---|
| **Python** | 3.11 ขึ้นไป (ใช้ `Self`, `tomllib`, pattern matching) |
| **OS หลัก** | Windows 11 (เครื่อง dev หลัก) |
| **OS รอง** | Linux (Ubuntu 22.04+) สำหรับ CI และ research |
| **สถาปัตยกรรม** | x86-64 · ARM64 ต้อง build STC native kernel เอง |
| **RAM ขั้นต่ำ** | 4 GB (Argon2id ใช้ 64 MB ต่อครั้ง, J-UNIWARD cost map ใช้หลายร้อย MB บนภาพใหญ่) |
| **GPU** | ไม่จำเป็นสำหรับ `src/` · จำเป็นสำหรับเทรน SRNet ใน `research/` |
| **Container runtime** | Docker Desktop / Docker Engine — ต้องมีถ้าจะใช้ analyzer |

#### Build / Package Manager

| หัวข้อ | ปัจจุบัน | เป้าหมาย | เหตุผล |
|---|---|---|---|
| **Dependency spec** | `requirements.txt` **(encoding เป็น UTF-16 + BOM → `pip install -r` พังบางเครื่อง)** | `pyproject.toml` (PEP 621) | แก้ปัญหา encoding + แยก optional group ได้ |
| **Package manager** | pip | `uv` หรือ pip + lockfile | ต้องมี lockfile เพื่อให้ผลการทดลองทำซ้ำได้ |
| **Layout** | flat (`src/` เป็นแค่โฟลเดอร์) | `src/sieng/` เป็น package จริง | `pip install -e .` แล้ว import ได้จากทุกที่ ไม่ต้องพึ่ง cwd |
| **Optional groups** | ไม่มี | `[gui]` `[analyzer]` `[research]` `[dev]` | ติดตั้งเฉพาะที่ใช้ ไม่ลาก torch มาให้ผู้ใช้ทั่วไป |
| **Native build** | ไม่มี | `setuptools` + `cffi` build STC kernel | มี wheel ให้แต่ละแพลตฟอร์ม |
| **Linter / Formatter** | ไม่มี | `ruff` + `mypy --strict` (เฉพาะ `crypto/`, `coder/`, `carrier/`) | ชั้นที่ผิดแล้วเงียบต้องมี type check |
| **Test runner** | ไม่มี | `pytest` + `hypothesis` + `pytest-cov` | |
| **CI** | ไม่มี | GitHub Actions: lint → type → unit → KAT → integration | |

#### Deployment Environment

| Target | รูปแบบ | รายละเอียด | Status |
|---|---|---|:---:|
| **Desktop (ผู้ใช้ทั่วไป)** | PyInstaller one-folder | GUI + core เท่านั้น ไม่รวม analyzer container | `N` |
| **Desktop (นักวิเคราะห์)** | PyInstaller + Docker | ต้องมี Docker เพื่อใช้ external tools | `R` |
| **Analyzer sandbox** | Docker image | `docker/Dockerfile.analyzer` — รัน binwalk/exiftool/zsteg แบบแยก network + read-only mount | `R` |
| **Research** | Docker image + GPU | `docker/Dockerfile.research` — torch + CUDA | `N` |
| **CI** | GitHub Actions runner | ubuntu-latest + windows-latest | `N` |
| **Library** | `pip install sieng` | สำหรับคนที่อยากใช้เป็น library ไม่ใช่ GUI | `N` |

> **เหตุผลที่ analyzer ต้องอยู่ใน container:** binwalk และ exiftool เป็น parser ของ format แปลกๆ นับร้อย และเคยมี CVE ที่ทำ RCE ได้จากไฟล์ที่ออกแบบมาเฉพาะ ในเมื่อ input ของเราคือ "ไฟล์ต้องสงสัยที่ผู้ใช้ไม่ไว้ใจ" การรัน parser พวกนี้บนเครื่องผู้ใช้ตรงๆ คือการเปิดช่องโจมตี — container ที่ตัด network และ mount แบบ read-only คือ mitigation ที่ถูกต้อง

### 1.5 Non-goals — สิ่งที่โปรเจกต์นี้ตั้งใจไม่ทำ

การระบุขอบเขตที่ไม่ทำสำคัญพอๆ กับที่ทำ เพราะมันกันไม่ให้ scope บาน

| ไม่ทำ | เหตุผล |
|---|---|
| Network transport / messaging | ระบบนี้ผลิต "ไฟล์" ผู้ใช้เลือกช่องทางส่งเอง การมี transport ในตัวจะสร้าง metadata ที่ตรวจจับได้เอง |
| Post-compromise security (DH ratchet เต็มรูป) | เฟส 1 ให้แค่ forward secrecy · PCS ต้อง re-KEM ตามรอบ — เป็น ADR แยก |
| ซ่อนข้อมูลใน video codec โดยตรง (H.264 motion vector) | ขอบเขตงานใหญ่มาก แยกโปรเจกต์ |
| ทำลาย / ต่อต้าน forensic tool | เป็น anti-forensics ไม่ใช่ steganography และมีปัญหาเชิงจริยธรรม |
| รับประกันว่า "ตรวจไม่เจอแน่นอน" | ไม่มีระบบไหนรับประกันได้ เรารายงานเป็น P_E ต่อ detector ที่ระบุชื่อเท่านั้น |

### 1.6 ขอบเขต Carrier ของ Phase 1

**Phase 1 ฝังได้เฉพาะ `.jpg` และ `.png` เท่านั้น**

| ระบบย่อย | รองรับอะไร | เหตุผล |
|---|---|---|
| **Embed / Extract** (`carrier/`) | **jpg, png เท่านั้น** | สองไฟล์นี้เป็น tier `strong` ที่ได้ประโยชน์จริงจาก J-UNIWARD + STC |
| **Analyze** (`analyzer/`) | jpg, png, wav, avi | ตรวจไฟล์ที่คนอื่นส่งมา — เราไม่ได้เลือกชนิดไฟล์ |
| **Research** (`research/`) | jpg เท่านั้น | DCTR/GFR/SRNet เป็น JPEG steganalysis |

**สิ่งที่การตัดสโคปนี้ทำให้ประหยัดไป:** parser 7 ตัวที่ต้อง fuzz · carrier ที่ต้อง maintain 9 ตัว · matrix ทดสอบที่บานเป็นเท่าตัว · และที่สำคัญที่สุดคือ **การไม่ต้องอธิบายกับผู้ใช้ว่าทำไมบางโหมดปลอดภัยกว่าโหมดอื่น**

การเปิดสโคปกลับมาอยู่ที่ P2-6 ถึง P2-8 (§12.3) และโครงสร้างรองรับไว้แล้วทั้งหมด — เพิ่ม carrier หนึ่งตัวคือเพิ่มไฟล์เดียว ไม่กระทบชั้นอื่น (§8.1)

---

## 2. Architecture

### 2.1 แบบจำลองเชิงชั้น

ระบบแบ่งเป็น 7 ชั้น + 1 ชั้นวิจัยที่แยกออกมา แต่ละชั้น **รู้จักเฉพาะชั้นที่อยู่ใต้ตัวเอง** และไม่รู้จักชั้นที่อยู่เหนือขึ้นไปเลย

| ชั้น | Package | ความรับผิดชอบเดียว | ห้ามรู้เรื่อง |
|:---:|---|---|---|
| 7 | `ui/` | รับ input จากผู้ใช้ แสดงผล | algorithm ใดๆ |
| 6 | `pipeline/` | เลือก engine ตามชนิดไฟล์ ลำดับขั้นตอน จัดการ error | รายละเอียดของ format หรือ math |
| 5 | `carrier/` | แปลงไฟล์ ↔ ตัวเลข และเขียนกลับโดยไม่ทิ้งร่องรอย | ว่าตัวเลขจะถูกใช้ทำอะไร |
| 4 | `domain/` | นิยาม `Plane` — ตัวแทนข้อมูลกลางที่ทุก format ลงมาเจอกัน | format, algorithm, crypto |
| 3 | `cost/` | ตอบว่า "แก้ค่าตัวไหนแล้วเสี่ยงโดนจับน้อยที่สุด" | ว่าจะฝัง bit อะไร |
| 2 | `coder/` | แปลง (cost vector + bits) → การเปลี่ยนแปลงที่ต้องทำ | ที่มาของ bits |
| 1 | `crypto/` | ผลิต bits ที่แยกจากค่าสุ่มไม่ออก + พิสูจน์ตัวตน | ว่า bits จะไปอยู่ที่ไหน |
| — | `research/` | วัดผลว่าที่ทำมาทั้งหมดรอดหรือไม่รอด | (อยู่นอกสายพึ่งพา) |

**หัวใจของการออกแบบอยู่ที่ชั้น 4** — `Plane` คือคอขวดที่ทำให้ JPEG กับ PNG ใช้ `cost`, `coder`, `crypto` ชุดเดียวกันได้ 100% ชั้น 3 ลงไปไม่รู้จักคำว่า "JPEG" เลยแม้แต่คำเดียว รู้แค่ "array กับ mask"

### 2.2 กฎการ import (บังคับด้วย CI)

ตารางนี้อ่านว่า "แถว import คอลัมน์ได้หรือไม่"

| ↓ import → | ui | pipeline | analyzer | carrier | domain | cost | coder | crypto | common |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **ui** | — | ได้ | ได้ | ✗ | ได้ | ✗ | ✗ | ✗ | ได้ |
| **pipeline** | ✗ | — | ✗ | ได้ | ได้ | ได้ | ได้ | ได้ | ได้ |
| **analyzer** | ✗ | ✗ | — | ได้ | ได้ | ✗ | ✗ | ✗ | ได้ |
| **carrier** | ✗ | ✗ | ✗ | — | ได้ | ✗ | ✗ | ✗ | ได้ |
| **domain** | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ได้ |
| **cost** | ✗ | ✗ | ✗ | ✗ | ได้ | — | ✗ | ✗ | ได้ |
| **coder** | ✗ | ✗ | ✗ | ✗ | ได้ | ✗ | — | ✗ | ได้ |
| **crypto** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | — | ได้ |
| **research** | ✗ | ได้ | ได้ | ได้ | ได้ | ได้ | ได้ | ✗ | ได้ |

กฎเพิ่มเติมที่ CI ต้องเช็ก:

1. `src/sieng/**` ห้าม import `torch` — ทั้งทางตรงและทางอ้อม
2. `crypto/**` ห้าม import อะไรจาก `sieng` ยกเว้น `common` — ชั้นนี้ต้อง audit ได้แบบแยกเดี่ยว
3. `ui/**` ห้าม import `crypto`, `coder`, `cost` ตรงๆ — ต้องผ่าน `pipeline` เท่านั้น GUI ไม่ควรมีโอกาสถือคีย์ดิบ
4. ห้ามมี circular import ทุกกรณี — `import-linter` ตรวจใน CI

### 2.3 ลำดับการทำงานตอน Embed

```
ui/gui/pages/embed_page.py
  │  ผู้ใช้เลือก cover + payload + engine + payload rate
  ▼
pipeline/embed.py :: run_embed()
  │
  ├─► carrier/detect.py :: sniff(path)
  │     อ่าน 32 bytes แรก เทียบ magic → คืนคลาส Carrier ที่ถูกต้อง
  │     (ไม่เชื่อนามสกุลไฟล์ — ผู้ใช้อาจเปลี่ยนชื่อ หรือไฟล์อาจถูกปลอม)
  │
  ├─► carrier.load()  →  carrier.planes()  →  list[Plane]
  │     JPEG: entropy-decode ได้ quantized DCT coefficient (ไม่ dequantize)
  │     PNG : อ่าน pixel array ตรง
  │
  ├─► pipeline/registry.py :: resolve(engine_id, carrier.domain)
  │     ตรวจว่า engine ที่เลือกใช้กับ domain นี้ได้จริง ถ้าไม่ได้ → fail ทันที
  │
  ├─► cost/juniward.py :: costs(carrier, plane)  →  (rho_p1, rho_m1)
  │     ค่าที่แก้ไม่ได้ (zero AC / wet pixel) ตั้งเป็น np.inf
  │
  ├─► crypto/ratchet/chain.py :: next_message_keys()   [สายขนาน]
  │     ├─ MK[n] → K_aead, nonce, seed_sel
  │     ├─ aead/gcm_siv.py :: seal(K_aead, nonce, payload, aad)
  │     │     aad = header_plaintext ‖ carrier.fingerprint()
  │     └─ header.py :: pack_and_whiten(...)  →  12–16 bytes
  │           whiten ด้วย K_hdr_session ที่ derive จาก ss โดยตรง
  │
  ├─► domain/selection.py :: permute(plane, seed_sel)
  │     ลำดับการไล่ coefficient เป็นความลับที่ต่างกันทุกไฟล์
  │
  ├─► coder/stc.py :: embed(values, rho_p1, rho_m1, bits, h=10)
  │     Viterbi หาชุดการเปลี่ยนแปลงที่ distortion รวมต่ำสุด
  │     ถ้า payload เกิน capacity → ยกเว้น CapacityError (fail closed)
  │
  ├─► carrier.apply(planes)  →  carrier.save(dst)
  │     JPEG: Huffman-encode ใหม่เฉพาะข้อมูล coefficient — quant table,
  │           header, EXIF, ทุก marker ที่ไม่เกี่ยวข้อง คงเดิม byte ต่อ byte
  │
  └─► crypto/ratchet/state_store.py :: commit()
        เซฟ counter ก่อนคืนค่าสำเร็จเสมอ — ยอมข้าม counter ดีกว่าใช้ซ้ำ
```

### 2.4 ลำดับการทำงานตอน Extract

```
pipeline/extract.py :: run_extract()
  │
  ├─► carrier/detect.py → carrier.load() → planes()
  │
  ├─► crypto/header.py :: unwhiten_and_parse(bits_prefix, K_hdr_session)
  │     ★ header ถูก whiten ด้วยคีย์ระดับ session ไม่ใช่ระดับ message
  │       เพราะยังไม่รู้ ctr จึงยังหา MK[ctr] ไม่ได้ (ดู ARCHITECTURE_v3 §5)
  │     ได้ ver, suite, sid, ctr, len, flags
  │
  ├─► crypto/ratchet/chain.py :: keys_for(ctr)
  │     ratchet ไปข้างหน้าถึง ctr (มีเพดานกัน DoS)
  │     คีย์ที่ข้ามมาเก็บใน skipped pool แบบจำกัดขนาด
  │
  ├─► domain/selection.py :: permute(plane, seed_sel)  [ลำดับเดิม]
  ├─► coder/stc.py :: extract(values, n_bits, h)
  ├─► crypto/aead/gcm_siv.py :: open(K_aead, nonce, ct, aad)
  │     aad ต้องตรงกับ carrier.fingerprint() ของไฟล์ที่ถืออยู่
  │     ผิด = ข้อมูลถูกตัดมาจากภาพอื่น → ปฏิเสธ
  │
  └─► คืน payload หรือโยน DecryptError แบบ constant-time
        ทุกความล้มเหลวคืน error ข้อความเดียวกัน ใช้เวลาเท่ากัน
```

### 2.5 หลักการออกแบบที่ใช้ตัดสินใจ

| หลักการ | นำไปใช้ตรงไหน |
|---|---|
| **Single Responsibility** | `lsb_pp.py` เดิมทำ 6 อย่างในคลาสเดียว → แตกเป็น carrier + cost + coder + crypto |
| **Open/Closed** | เพิ่ม format หรือ algorithm = เพิ่มไฟล์ + ลงทะเบียนใน registry ไม่แตะ orchestrator |
| **Dependency Inversion** | `pipeline` พึ่ง `Carrier` (ABC) ไม่ได้พึ่ง `JpegCarrier` (concrete) |
| **Fail closed** | capacity ไม่พอ / AAD ไม่ตรง / header เสีย → ยกเลิกงานทั้งหมด ห้าม fallback เงียบๆ |
| **Secure by default** | ทุก path ที่ผู้ใช้ไม่ระบุอะไร ต้องได้ค่าที่ปลอดภัยที่สุด ไม่ใช่เร็วที่สุด |
| **Reproducible research** | seed, lockfile, dataset hash ต้องบันทึกทุกการทดลอง |
| **Authenticate before decrypt** | ไม่มี session ไหนถูกสร้างโดยที่ยังไม่รู้ว่าคุยกับใคร |

---

### 2.6 Threat Model — สรุประดับสถาปัตยกรรม

เอกสารฉบับเต็มอยู่ที่ `docs/THREAT_MODEL.md` หัวข้อนี้คือส่วนที่ต้องรู้ก่อนแตะโค้ด

#### 2.6.1 ฝ่ายตรงข้ามที่ระบบนี้นับ

| ผู้โจมตี | ความสามารถ | อยู่ในขอบเขต |
|---|---|:---:|
| **Passive warden** | เห็นไฟล์ทุกไฟล์ที่ส่ง รัน steganalysis ระดับ state-of-the-art | ใช่ |
| **Active warden** | แก้ไข/บีบอัดซ้ำ/ตัดต่อไฟล์ระหว่างทาง | ใช่ (ตรวจจับได้ ไม่ใช่ทนทาน) |
| **Network MITM** | สลับ public key ตอนตั้ง session | ใช่ |
| **Harvest-now-decrypt-later** | เก็บทุกอย่างวันนี้ ถอดด้วย quantum computer ในอนาคต | ใช่ |
| **File-system attacker** | อ่าน/เขียน/ย้อนไฟล์ state บนเครื่องผู้ใช้ | บางส่วน — ดู 2.8 |
| **Malicious file supplier** | ป้อนไฟล์ที่ออกแบบมาโจมตี parser ของ analyzer | ใช่ |
| **Endpoint compromise เต็มรูป** | ควบคุม process, อ่าน RAM, ฝัง keylogger | **ไม่** — นอกขอบเขต |
| **Coercion / rubber-hose** | บังคับให้ผู้ใช้เปิดเผยคีย์ | **ไม่** — ระบบไม่มี deniability |

#### 2.6.2 แยกคำศัพท์ให้ชัด — อย่าเคลมเกินจริง

คำสี่คำนี้ถูกใช้ปนกันบ่อยมากจนกลายเป็นการเคลมที่ผิด ตารางนี้คือสิ่งที่ระบบให้จริง

| Scenario | Phase 1 | หมายเหตุ |
|---|:---:|---|
| ขโมย **message key เก่า** `MK[n]` | **ป้องกันได้** | ย้อนกลับหา `CK[n]` ไม่ได้ (label ต่างกัน) และเดินหน้าไม่ได้ |
| ขโมย **chain key เก่า** ที่ zeroize แล้ว | **ป้องกันได้** | ค่าไม่มีอยู่แล้ว |
| ขโมย **chain key ปัจจุบัน** `CK[n]` | **ป้องกันไม่ได้** | ถอดข้อความ n เป็นต้นไปได้ทั้งหมด — นี่คือ **forward secrecy ไม่ใช่ PCS** |
| ขโมย **private KEM key** | **ป้องกันไม่ได้** | สร้าง session ใหม่ปลอมได้ · session เก่าที่ ephemeral ยังปลอดภัย |
| ขโมย **identity signing key** | **ป้องกันไม่ได้** | ปลอมตัวได้ ต้องมีกลไก revoke (`crypto/lifecycle/rotation.py`) |
| **Endpoint compromise** | **ป้องกันไม่ได้** | นอกขอบเขตโดยประกาศ |
| **Post-compromise recovery** | **ไม่มีใน Phase 1** | ต้องมี re-KEM — เลื่อนไป Phase 2 |
| **State rollback** โดยผู้มีสิทธิ์ในไฟล์ | **ลดความเสียหายได้ ไม่ได้ป้องกัน** | ดู 2.8 |

> **ประโยคที่ห้ามเขียนใน README, เอกสารวิชาการ หรือ UI:**
> "ระบบมี post-compromise security" · "คีย์หลุดแล้วยังปลอดภัย" · "ตรวจจับไม่ได้"
> **ประโยคที่เขียนได้:** "มี forward secrecy ภายใต้สมมติฐานว่า chain key เก่าถูกลบสำเร็จ"

#### 2.6.3 สิ่งที่ระบบ **ไม่** รับประกัน

| ไม่รับประกัน | เหตุผล |
|---|---|
| **Robustness** ต่อการบีบอัดซ้ำ/resize/crop | J-UNIWARD + STC ออกแบบมาเพื่อ undetectability ไม่ใช่ robustness — ถ้า Facebook บีบภาพซ้ำ payload หายทั้งหมด |
| **Deniability** | ไฟล์ stego ที่มี header ถูกต้องคือหลักฐานว่ามีการฝัง เมื่อผู้ตรวจได้คีย์มา |
| **Metadata privacy ระดับ transport** | ระบบนี้ผลิตไฟล์ ไม่จัดการช่องทางส่ง — ผู้ใช้ต้องคิดเรื่องนี้เอง |
| **การล้าง memory สมบูรณ์** | Python จัดการหน่วยความจำเอง `zeroize()` ทำได้ดีที่สุดเท่าที่ภาษาอนุญาต — ประกาศเป็นข้อจำกัดที่รู้ตัว |

---

### 2.7 Session Establishment & Authentication

#### 2.7.1 ปัญหา: KEM ให้ความลับ แต่ไม่ให้ตัวตน

`X25519 + ML-KEM-768` ตอบได้แค่ "มีความลับร่วมกับใครบางคน" ไม่ได้ตอบว่า "คนนั้นคือ Bob จริงไหม"
ถ้าไม่มี authentication ผู้โจมตีสร้าง session แยกกับทั้งสองฝั่งได้ แล้วอ่านทุกอย่างตรงกลางโดยที่ทั้งคู่ไม่รู้ตัว — และเพราะช่องทางส่งของระบบนี้เป็นช่องทางสาธารณะโดยธรรมชาติ ความเสี่ยงนี้สูงกว่าระบบแชตทั่วไปด้วยซ้ำ

#### 2.7.2 ข้อจำกัดที่ตัดสินการออกแบบ — ตัวเลขความจุจริง

ก่อนเลือก protocol ต้องดูก่อนว่า **มีที่ให้ใส่แค่ไหน** นี่คือข้อจำกัดที่การรีวิวส่วนใหญ่มองข้าม

| องค์ประกอบ | ขนาด |
|---|---:|
| X25519 ephemeral public key | 32 B |
| ML-KEM-768 ciphertext | 1,088 B |
| ML-KEM-768 public key | 1,184 B |
| Ed25519 public key / signature | 32 B / 64 B |
| **ML-DSA-65 public key / signature** | **1,952 B / 3,309 B** |
| **รวม session bootstrap แบบลงนาม PQ เต็มรูป** | **≈ 6.5 KB ≈ 52,000 bits** |

เทียบกับความจุจริงของภาพมาตรฐานงานวิจัย (512×512 grayscale, QF75, non-zero AC ≈ 26,000):

| Payload rate | ความจุ |
|---|---:|
| 0.05 bpnzAC | 1,300 bits ≈ **163 B** |
| 0.10 bpnzAC | 2,600 bits ≈ **325 B** |
| 0.20 bpnzAC | 5,200 bits ≈ **650 B** |
| 0.40 bpnzAC | 10,400 bits ≈ **1,300 B** |

**ข้อสรุป: session bootstrap แบบเต็มไม่มีทางลงในภาพ 512×512 ได้เลยแม้ที่ 0.4 bpnzAC — ขาดไปประมาณ 5 เท่า**
แค่ ML-KEM ciphertext ก้อนเดียว (1,088 B) ก็เกินความจุที่ 0.1 bpnzAC ไปแล้ว 3.3 เท่า

ดังนั้นการเลือกระหว่าง "self-contained" กับ "out-of-band" **ไม่ใช่เรื่องรสนิยม แต่ถูกบังคับโดยความจุ**

#### 2.7.3 การตัดสินใจ — envelope เป็นแบบขึ้นกับความจุ

| โหมด | เงื่อนไขที่ใช้ได้ | per-image overhead | ใช้เมื่อไหร่ |
|---|---|---:|---|
| **`ENVELOPE_EXTERNAL`** *(ค่าเริ่มต้น)* | ทุกกรณี | 12–16 B | ภาพงานวิจัย, ภาพเล็ก, ส่งหลายไฟล์ต่อ session |
| `ENVELOPE_INLINE` | `capacity ≥ 8 × envelope_size` | ≈ 1.2 KB | ภาพจากกล้องจริง (เช่น 4000×3000 → nnzAC ≈ 1.5 M → ที่ 0.1 bpnzAC ได้ ≈ 18 KB) |
| `ENVELOPE_MULTIPART` | ส่ง ≥ N ไฟล์ใน session เดียว | กระจายในไฟล์แรกๆ | เมื่อ inline ไม่พอแต่ไม่อยากส่ง envelope แยก |

การเลือกทำอัตโนมัติโดย `crypto/envelope.py :: choose_mode(carrier, rate)` และบันทึกไว้ใน `flags` ของ header — ผู้ใช้ override ได้แต่ระบบจะเตือนเมื่อการเลือกทำให้ payload rate จริงพุ่งขึ้น

#### 2.7.4 Authentication — เลือกวิธีที่ไม่กินความจุ

ข้อจำกัดข้างบนทำให้ signature-based authentication แบบตรงไปตรงมาแพงมาก (ML-DSA-65 signature กินความจุที่ 0.1 bpnzAC ของภาพ 512×512 ถึง 10 ภาพ) ทางออกคือแยก authentication ออกเป็นสองระดับ

**ระดับที่ 1 — `AUTH_IMPLICIT` (ค่าเริ่มต้น, overhead = 0 byte)**

ยืมแนวคิด auth mode ของ HPKE: เพิ่ม DH ระหว่าง **static key ของผู้ส่ง** กับ **static key ของผู้รับ** เข้าไปใน transcript

```
ss = HKDF(
      DH(eph_sender_sk,    static_recipient_pk)     # confidentiality
    ‖ DH(static_sender_sk, static_recipient_pk)     # ★ sender authentication
    ‖ ML-KEM.Decap(recipient_mlkem_sk, ct)          # PQ confidentiality
    ‖ transcript,
    info = SUITE_ID)
```

`transcript` ต้องผูก: `identity_sender ‖ identity_recipient ‖ eph_pk ‖ mlkem_ct ‖ mlkem_pk ‖ suite ‖ version ‖ sid`

ผู้ที่ไม่มี static private key ของผู้ส่งจะคำนวณ `ss` ไม่ได้ → ได้ sender authentication มาโดยไม่เสีย byte เพิ่มเลยแม้แต่ตัวเดียว

**ระดับที่ 2 — `AUTH_PQ_EXPLICIT` (ทางเลือก, +3,373 B)**

เพิ่มลายเซ็น Ed25519 + ML-DSA-65 บน transcript ใช้เมื่อ envelope เป็น external (ไม่กินความจุของภาพ) หรือเมื่อต้องการ non-repudiation

**ข้อจำกัดที่ต้องประกาศให้ชัด:** `AUTH_IMPLICIT` ให้ **การพิสูจน์ตัวตนเชิงคลาสสิก** เท่านั้น ผู้โจมตีที่มี quantum computer ในอนาคตจะปลอมตัวได้ แต่ **ยังถอดข้อความที่ดักไว้วันนี้ไม่ได้** เพราะ confidentiality มาจาก ML-KEM
นี่เป็น trade-off ที่ยอมรับได้สำหรับ threat model นี้ เพราะการปลอมตัวเป็นการโจมตีแบบ online ที่ต้องเกิด ณ ตอนนั้น ส่วนการถอดรหัสเป็นการโจมตีแบบ offline ที่ทำย้อนหลังได้ — **สิ่งที่ต้องกันคือ harvest-now-decrypt-later และเรากันได้แล้ว**

การไม่มี PQ authentication แบบ non-interactive โดยไม่ใช้ signature เป็นข้อจำกัดของ ML-KEM เอง ไม่ใช่ของการออกแบบนี้ — ML-KEM ไม่รองรับ static-static แบบที่ DH ทำได้

---

### 2.8 State Security — Rollback และ Concurrency

#### 2.8.1 สองสถานการณ์ที่ทำให้ nonce/key ซ้ำ

```
Rollback                        Concurrency
─────────                       ────────────
counter = 100                   Process A อ่าน state → counter 101
  ↓ backup ไฟล์ state           Process B อ่าน state → counter 101
counter = 101 (ส่งภาพ)              ↓            ↓
  ↓ restore backup              ทั้งคู่ใช้ MK[101] กับข้อความคนละอัน
counter = 100 → ใช้ MK[100] ซ้ำ
```

ทั้งสองกรณีจบที่เดียวกัน: **message key ตัวเดียวถูกใช้กับ plaintext สองอัน**

#### 2.8.2 สิ่งที่ป้องกันได้จริง กับสิ่งที่ป้องกันไม่ได้

ต้องพูดตรงๆ: **ถ้าผู้โจมตีมีสิทธิ์เขียนไฟล์บนเครื่อง การ rollback ป้องกันแบบสมบูรณ์ไม่ได้ด้วย state ที่เก็บในไฟล์เพียงอย่างเดียว** เขาสำรองแล้วคืนค่ากลับได้เสมอ การอ้างว่าป้องกันได้เป็นการเคลมเกินจริง

สิ่งที่ทำได้จริงมีสามชั้น เรียงตามความแข็งแรง

| ชั้น | กลไก | ป้องกันอะไร | ข้อจำกัด |
|:---:|---|---|---|
| 1 | **Monotonic generation counter** ในไฟล์ state + ตรวจว่าไม่ลดลง | ผู้ใช้ restore backup โดยไม่ตั้งใจ · sync ทับจาก cloud drive | ผู้โจมตีที่ตั้งใจย้อนได้ |
| 2 | **Exclusive file lock** ตลอดช่วง read-modify-write | สอง process ทำงานพร้อมกัน | ไม่กัน rollback |
| 3 | **Monotonic counter ระดับ OS/hardware** (TPM NV counter, Keychain, DPAPI) | rollback แบบตั้งใจ | ผูกกับแพลตฟอร์ม ทำให้ย้ายเครื่องยาก — เลื่อนไป Phase 2 |

**ตาข่ายนิรภัยชั้นสุดท้าย:** นี่คือเหตุผลที่เลือก **AES-256-GCM-SIV ไม่ใช่ GCM ธรรมดา** ตั้งแต่ต้น
ถ้า rollback เกิดขึ้นจริงและ key+nonce ซ้ำ GCM ธรรมดาจะ**รั่ว authentication key `H` ทำให้ปลอม tag ได้ทุกข้อความในคีย์นั้น** ส่วน GCM-SIV เสียแค่ความสามารถบอกว่า "plaintext สองอันนี้เหมือนกันหรือไม่" — เสียหายแต่ไม่ล่มสลาย

การออกแบบที่ถูกต้องคือยอมรับว่าชั้น 1–2 กันความผิดพลาดได้ ชั้น 3 กันเจตนาร้ายได้บางส่วน และ **เลือก primitive ที่ทนทานเมื่อทั้งสามชั้นล้มเหลว**

#### 2.8.3 ลำดับการ commit ที่ถูกต้อง

```
1. acquire exclusive lock              ← ล็อกก่อนอ่าน ไม่ใช่ก่อนเขียน
2. load state + ตรวจ generation ไม่ลดลง
3. ratchet → ได้ MK[n], generation+1
4. เขียน state ใหม่: temp → fsync(temp) → rename → fsync(dir)
5. ★ เขียนไฟล์ stego  ← หลังจาก state ลงดิสก์แล้วเท่านั้น
6. release lock
```

ถ้าโปรแกรมตายระหว่างขั้นที่ 4–5 ผลลัพธ์คือ counter ถูกข้ามไปหนึ่งตัวโดยไม่มีไฟล์ออกมา — **เสียของ แต่ไม่เสียความปลอดภัย** ซึ่งเป็นทิศทางที่ถูกต้องของการ fail

---

## 3. Directory Structure

รหัสท้ายบรรทัดคือสถานะตามหัวข้อ 0.1

```
SIENG2_2/
│
├── pyproject.toml                          [N]  แทน requirements.txt ที่ encoding เสีย
├── uv.lock  /  requirements.lock           [N]  ตรึงเวอร์ชันเพื่อ reproducibility
├── README.md                               [N]
├── main.py                                 [R]  เหลือแค่ entry point 5 บรรทัด
├── .gitignore                              [E]
│
├── docker/
│   ├── Dockerfile.analyzer                 [R]  แยกจาก Dockerfile เดิม
│   ├── Dockerfile.research                 [N]  torch + CUDA
│   ├── compose.yaml                        [N]
│   ├── .dockerignore                       [E]
│   └── build.ps1                           [E]
│
├── src/sieng/                              ★ package หลัก
│   ├── __init__.py                         [N]  export public API + __version__
│   │
│   ├── app/                                ── composition root
│   │   ├── __init__.py                     [N]
│   │   ├── settings.py                     [N]  path, workspace, default config
│   │   └── container.py                    [N]  ที่เดียวในระบบที่ประกอบ registry
│   │
│   ├── carrier/                            ── ชั้น 5: ไฟล์ ↔ ตัวเลข
│   │   ├── __init__.py                     [N]
│   │   ├── base.py                         [N]  Carrier (ABC)
│   │   ├── detect.py                       [N]  sniff magic bytes
│   │   ├── registry.py                     [N]
│   │   ├── errors.py                       [N]  UnsupportedCarrier, LossyCarrier
│   │   └── image/                          ── ★ Phase 1 รองรับแค่สองไฟล์นี้
│   │       ├── jpeg.py                     [N]  ★ quantized DCT, ห้าม recompress
│   │       └── png.py                      [R]  ดึงส่วน chunk จาก lsb_pp.py เดิม
│   │   ┆
│   │   ┆ ── ☐ Phase 2 (โครงรองรับแล้ว ยังไม่ทำ) ────────────────
│   │   ┆   image/bmp.py · image/tiff.py · image/webp.py
│   │   ┆   audio/wav.py · audio/mp3.py
│   │   ┆   video/avi.py · video/mp4.py · generic/blob.py
│   │
│   ├── domain/                             ── ชั้น 4: ตัวแทนกลาง
│   │   ├── __init__.py                     [N]
│   │   ├── plane.py                        [N]  Plane dataclass
│   │   ├── selection.py                    [N]  non-zero AC, wet paper, permutation
│   │   └── capacity.py                     [N]  bpnzAC ↔ bpp ↔ bits
│   │
│   ├── cost/                               ── ชั้น 3: distortion model
│   │   ├── __init__.py                     [N]
│   │   ├── base.py                         [N]  CostModel (ABC)
│   │   ├── juniward.py                     [N]  ★ DCT domain
│   │   ├── si_uniward.py                   [N]  ต้องมี precover
│   │   ├── uerd.py                         [N]  baseline ที่เร็วกว่า
│   │   ├── hill.py                         [N]  spatial domain
│   │   ├── wavelet.py                      [N]  DWT filter bank ที่ใช้ร่วมกัน
│   │   └── legacy_texture.py               [R]  gradient+entropy ของ LSB-PP เดิม
│   │
│   ├── coder/                              ── ชั้น 2: syndrome coding
│   │   ├── __init__.py                     [N]
│   │   ├── base.py                         [N]
│   │   ├── stc.py                          [N]  ★ Viterbi trellis
│   │   ├── simulator.py                    [N]  optimal coder simulation
│   │   ├── opap.py                         [R]  OPAP ของ LSB-PP เดิม
│   │   └── _native/
│   │       ├── stc_kernel.c                [N]
│   │       └── build.py                    [N]
│   │
│   ├── crypto/                             ── ชั้น 1
│   │   ├── __init__.py                     [N]
│   │   ├── kem/
│   │   │   ├── x25519.py                   [N!]
│   │   │   ├── mlkem768.py                 [N!]
│   │   │   └── hybrid.py                   [N!] ★ ผูก ct+pk เข้า transcript
│   │   ├── auth/                           ── ★ P0: กัน MITM
│   │   │   ├── identity.py                 [N!] static keypair + fingerprint
│   │   │   ├── transcript.py               [N!] ★ ประกอบ transcript ตามลำดับตายตัว
│   │   │   ├── key_binding.py              [N!] AUTH_IMPLICIT (HPKE auth mode)
│   │   │   ├── signatures.py               [N!] AUTH_PQ_EXPLICIT: Ed25519 + ML-DSA-65
│   │   │   └── trust_store.py              [N!] prekey bundle + revocation list
│   │   ├── envelope.py                     [N!] ★ P0: EXTERNAL/INLINE/MULTIPART
│   │   ├── kdf/
│   │   │   ├── hkdf.py                     [N!]
│   │   │   ├── argon2.py                   [R]  ดึงจาก sym_encrypt.py เดิม
│   │   │   └── labels.py                   [N!] domain separation string ทั้งหมด
│   │   ├── aead/
│   │   │   └── gcm_siv.py                  [N!]
│   │   ├── ratchet/
│   │   │   ├── session.py                  [N!]
│   │   │   ├── chain.py                    [N!] ★ CK[n] → CK[n+1], MK[n]
│   │   │   ├── state_store.py              [N!] atomic persist ของ counter
│   │   │   ├── state_lock.py               [N!] ★ P0: exclusive lock ข้าม process
│   │   │   ├── generation.py               [N!] ★ P0: monotonic generation counter
│   │   │   └── rollback_guard.py           [N!] ★ P0: ตรวจจับ state ย้อนกลับ
│   │   ├── lifecycle/                      ── ★ P1: วงจรชีวิตของคีย์
│   │   │   ├── key_state.py                [N!] state machine ของทุกคีย์
│   │   │   ├── rotation.py                 [N!] rotate + revoke identity key
│   │   │   └── destroy.py                  [N!] ลบคีย์และ state อย่างเป็นทางการ
│   │   ├── rekey/                          ── ☐ Phase 2: post-compromise recovery
│   │   │   └── re_kem.py                   [—]  ยังไม่ทำใน Phase 1
│   │   ├── header.py                       [N!] ★ 12–16 B, whitened
│   │   ├── keystore.py                     [N!] private key at-rest
│   │   └── zeroize.py                      [N!]
│   │
│   ├── pipeline/                           ── ชั้น 6: orchestration
│   │   ├── __init__.py                     [N]
│   │   ├── embed.py                        [R]
│   │   ├── extract.py                      [R]
│   │   ├── registry.py                     [N]  ★ แทน if/elif ใน config_mode.py
│   │   ├── context.py                      [N]  ส่งผ่าน progress/log/cancel
│   │   ├── engines/
│   │   │   ├── base.py                     [N]  Engine (ABC)
│   │   │   ├── juniward_stc.py             [N]  ★ engine หลักตัวใหม่
│   │   │   ├── hill_stc.py                 [N]
│   │   │   ├── lsbpp.py                    [R]  ห่อของเดิมให้เข้า interface
│   │   │   ├── locomotive.py               [R]
│   │   │   └── metadata.py                 [R]
│   │   └── yaml/
│   │       ├── schema.py                   [N]  pydantic / dataclass schema
│   │       ├── loader.py                   [R]  จาก config_mode.py
│   │       ├── validate.py                 [R]  จาก validate_pipeline()
│   │       └── templates/                  [E]  01–05 yaml เดิม
│   │
│   ├── analyzer/                           ── ฝั่งตรวจจับ
│   │   ├── __init__.py                     [E]
│   │   ├── dispatcher.py                   [E]  จาก handle.py
│   │   ├── compare.py                      [E]  จาก compare_logic.py
│   │   ├── docker_bridge.py                [E]
│   │   ├── sandbox.py                      [N]  ★ P1: บังคับ policy ก่อนรัน container
│   │   ├── resource_policy.py              [N]  ★ P1: CPU/RAM/PID/quota ต่อ profile
│   │   ├── limits.py                       [N]  ★ P1: เพดาน input ก่อนถึง parser
│   │   ├── timeout.py                      [N]  ★ P1: watchdog + kill process tree
│   │   ├── formats/
│   │   │   ├── base_handler.py             [E]
│   │   │   ├── jpeg_handler.py             [N]  ★ ใหม่
│   │   │   ├── png_handler.py              [E]
│   │   │   ├── wav_handler.py              [E]
│   │   │   └── avi_handler.py              [E]
│   │   ├── modules/
│   │   │   ├── metadata_analyzer.py        [E]
│   │   │   ├── statistical_analyzer.py     [E]
│   │   │   ├── structure_integrity.py      [E]
│   │   │   ├── stat/                       [E]  chi_square, rs, ws, spa, pdh, hcf
│   │   │   └── dct/                        [N]  ★ double compression, qtable
│   │   ├── external_tools/                 [E]  binwalk, exiftool, hachoir, ...
│   │   └── utils/text_extractor.py         [E]
│   │
│   ├── ui/
│   │   ├── gui/                            [E]  main_window, pages, tabs, components
│   │   └── cli/                            [R]  argparse → typer
│   │
│   └── common/
│       ├── errors.py                       [N]  exception hierarchy ทั้งระบบ
│       ├── logging.py                      [N]  ★ redaction filter กันคีย์หลุด log
│       ├── progress.py                     [R]  ProgressCallback ที่กระจายอยู่ 3 ไฟล์
│       └── types.py                        [N]
│
├── tests/
│   ├── conftest.py                         [N]
│   ├── unit/                               [N]
│   ├── vectors/                            [N!] KAT: ML-KEM, ML-DSA, HKDF, GCM-SIV, STC
│   ├── property/                           [N]  roundtrip ทุก format ทุก payload
│   ├── integration/                        [N]
│   ├── security/                           [N!] tamper, replay, MITM, rollback, leak
│   ├── fuzz/                               ── ★ P1
│   │   ├── fuzz_jpeg.py                    [N]  malformed JPEG → carrier
│   │   ├── fuzz_header.py                  [N]  ★ bit ที่ถอดมาจากภาพที่ไม่มีข้อมูล
│   │   ├── fuzz_envelope.py                [N]  session envelope ที่ถูกดัดแปลง
│   │   ├── fuzz_stc.py                     [N]  cost/bits ที่ผิดรูป
│   │   ├── fuzz_pipeline.py                [N]  YAML ที่เป็นอันตราย
│   │   ├── fuzz_state.py                   [N]  state file ที่เสียหาย
│   │   └── corpus/                         [N]  seed corpus + crash ที่เคยเจอ
│   └── fixtures/                           [N]  ภาพตัวอย่างขนาดเล็ก
│
├── research/                               ── แยก dependency
│   ├── datasets/
│   │   ├── bossbase.py  alaska2.py                    [N]
│   │   ├── split.py                                   [N]  paired split
│   │   ├── quality.py                                 [N]  ★ สร้างชุด Q50–Q95
│   │   └── source_meta.py                             [N]  ★ ผูก cover กับกล้อง/แหล่งที่มา
│   ├── features/  dctr.py  gfr.py                     [N]
│   ├── models/
│   │   ├── ensemble.py                                [N]  FLD ensemble
│   │   └── srnet/  model.py  train.py                 [N]
│   ├── experiments/
│   │   ├── payload_sweep.yaml                         [N]  0.05–0.4 bpnzAC
│   │   ├── quality_sweep.yaml                         [N]  ★ P1: Q50–Q95
│   │   ├── cross_dataset.yaml                         [N]  ★ P1: BOSS↔ALASKA
│   │   └── cover_source_mismatch.yaml                 [N]  ★ P1: CSM
│   ├── stats.py                                       [N]  ★ P1: CI + N + seed
│   ├── results/                                       [N]
│   └── notebooks/                                     [N]
│
├── .github/workflows/
│   ├── ci.yml                              [N]  lint → type → SAST → dep → test
│   └── release.yml                         [N]  SBOM + hash + provenance
│
├── SECURITY.md                             [N]  ★ วิธีรายงานช่องโหว่ + ขอบเขต
│
└── docs/
    ├── PROJECT_STRUCTURE.md                [E]  เอกสารนี้
    ├── ARCHITECTURE_v3.md                  [E]
    ├── THREAT_MODEL.md                     [N!] ★ P0 — ต้องเขียนก่อน implementation
    ├── SESSION_PROTOCOL.md                 [N!] ★ P0 — handshake + auth + envelope
    ├── FORMAT_SPEC.md                      [N!] ★ P0 — bit-level ของ header + envelope
    ├── KEY_LIFECYCLE.md                    [N]  ★ P1
    ├── SECURITY_MATRIX.md                  [N]  ★ P1 — threat × mitigation × test
    ├── CONTRIBUTING.md                     [N]
    └── adr/                                [N]  architecture decision records
```

---

## 4. Module Reference

แต่ละหัวข้อย่อยมีโครงเดียวกัน: **หน้าที่ → ไฟล์ → API หลัก → พึ่งพาใคร → ใครพึ่งพา → หมายเหตุ**

---

### 4.1 `app/` — Composition Root

**หน้าที่:** เป็นที่เดียวในระบบที่ประกอบชิ้นส่วนเข้าด้วยกัน โมดูลอื่นไม่ควรรู้ว่ามี implementation ตัวไหนอยู่บ้าง

| ไฟล์ | หน้าที่ | Status |
|---|---|:---:|
| `settings.py` | ค่าคอนฟิกรวมศูนย์ อ่านจาก env / ไฟล์ / ค่า default | `N` |
| `container.py` | สร้างและลงทะเบียน registry ทั้งหมด | `N` |

```python
# settings.py
@dataclass(frozen=True)
class Settings:
    workspace_dir: Path
    temp_dir: Path
    docker_enabled: bool = True
    default_stc_height: int = 10          # h ของ STC
    default_payload_rate: float = 0.1     # bpnzAC
    max_ratchet_skip: int = 1000          # กัน DoS ตอน extract
    log_level: str = "INFO"

def load_settings(path: Path | None = None) -> Settings: ...
```

```python
# container.py
@dataclass
class Container:
    settings: Settings
    carriers: CarrierRegistry
    engines:  EngineRegistry
    costs:    CostRegistry

def build_container(settings: Settings | None = None) -> Container:
    """import ทุก implementation แล้วลงทะเบียน — เรียกครั้งเดียวตอน startup"""
```

**พึ่งพา:** ทุกชั้น (เป็นข้อยกเว้นของกฎ import โดยเจตนา)
**ถูกพึ่งพาโดย:** `main.py`, `ui/cli`, `tests/conftest.py`

---

### 4.2 `carrier/` — ชั้นแปลงไฟล์เป็นตัวเลข

**หน้าที่:** รู้เรื่อง binary format ของไฟล์ทั้งหมด แล้วเปิดเผยออกมาเป็น `Plane` ที่เป็นกลาง
นี่คือชั้นเดียวในระบบที่รู้ว่า "JPEG" กับ "PNG" ต่างกันยังไง

#### `base.py`

```python
class Carrier(ABC):
    # --- class-level metadata ใช้ตอนลงทะเบียนและตรวจความเข้ากันได้ ---
    suffixes: ClassVar[tuple[str, ...]]
    magic: ClassVar[tuple[bytes, ...]]
    domain: ClassVar[Literal["dct", "spatial"]]   # Phase 1 มีแค่สองค่านี้
    lossless_roundtrip: ClassVar[bool]          # False → ห้ามใช้ฝังจริง
    security_tier: ClassVar[Literal["strong", "weak", "none"]]
    # ★ tier ยังเป็น Literal สามค่าแม้ Phase 1 จะมีแต่ strong
    #   เพื่อให้กลไกเตือนพร้อมใช้ตอน Phase 2 เพิ่ม carrier ที่อ่อนกว่า

    def __init__(self, path: Path) -> None: ...

    @classmethod
    def sniff(cls, head: bytes) -> bool:
        """ตรวจจาก byte จริง ไม่ใช่นามสกุล"""

    @abstractmethod
    def load(self) -> None:
        """อ่านไฟล์เข้าหน่วยความจำ แยกส่วนที่แก้ได้กับส่วนที่ต้องคงเดิม"""

    @abstractmethod
    def planes(self) -> list[Plane]:
        """คืนค่าที่แก้ได้พร้อม mask — JPEG คืน 1 plane ต่อ component"""

    @abstractmethod
    def apply(self, planes: list[Plane]) -> None:
        """เขียนค่าที่แก้แล้วกลับเข้าโครงสร้างภายใน"""

    @abstractmethod
    def save(self, dst: Path) -> None:
        """เขียนไฟล์ออก — ส่วนที่ไม่ได้แก้ต้อง byte-exact"""

    @abstractmethod
    def fingerprint(self) -> bytes:
        """hash ของคุณสมบัติที่ไม่เปลี่ยนตอนฝัง ใช้เป็น AAD"""

    def capacity(self, unit: str = "bpnzAC") -> float: ...
```

#### ไฟล์ในแพ็กเกจ

| ไฟล์ | คลาสหลัก | domain | tier | Status |
|---|---|---|:---:|:---:|
| `detect.py` | `sniff(path) -> type[Carrier]`, `open_carrier(path) -> Carrier` | — | — | `N` |
| `registry.py` | `CarrierRegistry.register/resolve/all` | — | — | `N` |
| `errors.py` | `UnsupportedCarrierError`, `LossyCarrierError`, `CorruptCarrierError` | — | — | `N` |
| `image/jpeg.py` | `JpegCarrier` | dct | strong | `N` |
| `image/png.py` | `PngCarrier` | spatial | strong | `R` |

**นี่คือรายการทั้งหมดของ Phase 1 — สอง carrier เท่านั้น**

| นามสกุล | Carrier | Domain | Engine เริ่มต้น | Tier |
|---|---|---|---|:---:|
| `.jpg` `.jpeg` `.jpe` | `JpegCarrier` | quantized DCT | `juniward-stc` | **strong** |
| `.png` | `PngCarrier` | spatial | `hill-stc` | **strong** |

ไฟล์ชนิดอื่นทั้งหมด (`.bmp` `.tif` `.webp` `.wav` `.mp3` `.avi` `.mp4` และไฟล์ทั่วไป) `detect.sniff()` ต้องโยน `UnsupportedCarrierError` พร้อมข้อความที่บอกตรงๆ ว่ายังไม่รองรับ — **ห้ามพยายามเดาหรือ fallback ไปวิธีที่อ่อนกว่า**

> **เหตุผลที่ตัดสโคปลงเหลือสองไฟล์:** carrier ที่เหลือทั้งหมดอยู่ใน tier `weak`/`none` — การฝังใน MP3/AVI/PDF คือการต่อท้ายไฟล์หรือใส่ metadata ซึ่งตรวจเจอได้ด้วย `binwalk` ในไม่กี่วินาที มันไม่ใช่ steganography เชิงสถิติและไม่ได้ประโยชน์จาก J-UNIWARD + STC เลย
> การมีอยู่ของมันสร้างต้นทุนสามอย่างโดยไม่ให้ความปลอดภัยกลับมา: attack surface ของ parser เพิ่มขึ้น (แต่ละ format คือ parser หนึ่งตัวที่ต้อง fuzz), matrix ของการทดสอบบานเป็นเท่าตัว, และ **ผู้ใช้เข้าใจผิดว่าทุกโหมดปลอดภัยเท่ากัน** — ซึ่งเป็นความเสี่ยงที่แก้ด้วยโค้ดไม่ได้
> `security_tier` ยังคงอยู่ใน `Carrier` ABC เพราะเมื่อ Phase 2 เพิ่ม carrier ที่อ่อนกว่ากลับเข้ามา กลไกเตือนต้องมีอยู่แล้วตั้งแต่แรก ไม่ใช่มาเติมทีหลัง

#### `image/jpeg.py` — ไฟล์ที่สำคัญที่สุดของฟีเจอร์ใหม่

```python
class JpegCarrier(Carrier):
    suffixes = (".jpg", ".jpeg", ".jpe")
    magic = (b"\xff\xd8\xff",)
    domain = "dct"
    lossless_roundtrip = True
    security_tier = "strong"

    # --- public ---
    def load(self) -> None: ...
    def planes(self) -> list[Plane]:
        """1 plane ต่อ component (Y, Cb, Cr) values เป็น int16 quantized coeff"""
    def apply(self, planes: list[Plane]) -> None: ...
    def save(self, dst: Path) -> None: ...
    def fingerprint(self) -> bytes:
        """SHA-256(qtables ‖ w ‖ h ‖ subsampling ‖ n_components ‖ progressive)"""

    # --- properties ---
    @property
    def quant_tables(self) -> list[np.ndarray]: ...
    @property
    def is_progressive(self) -> bool: ...
    def nnz_ac(self, component: int = 0) -> int:
        """จำนวน AC coefficient ที่ไม่ใช่ศูนย์ — ตัวหารของหน่วย bpnzAC"""

    # --- internal ---
    def _decode_coefficients(self) -> None:
        """entropy-decode → quantized coeff. ★ ห้าม dequantize/IDCT"""
    def _encode_coefficients(self) -> bytes:
        """Huffman-encode กลับ · marker อื่นทั้งหมดคัดลอกดิบ"""
```

> **Invariant ที่ต้องมี test บังคับ:** `load() → save()` โดยไม่แก้ค่าใดเลย ต้องได้ไฟล์ที่ byte-identical กับต้นฉบับ
> ถ้าข้อนี้ไม่ผ่าน ทุกอย่างที่สร้างต่อจากนี้ไม่มีความหมาย เพราะ double compression artifact จะทำให้ DCTR/GFR จับได้ตั้งแต่ยังไม่ได้ฝังอะไรเลย **นี่คือ test ตัวแรกที่ต้องเขียนในเฟส 2**

#### `detect.py`

```python
MAGIC_TABLE: list[tuple[bytes, int, type[Carrier]]]   # (magic, offset, carrier)

def sniff(path: Path) -> type[Carrier]:
    """อ่าน 32 bytes แรก จับคู่ magic — โยน UnsupportedCarrierError ถ้าไม่รู้จัก"""

def open_carrier(path: Path, *, require_lossless: bool = True) -> Carrier:
    """sniff + สร้าง instance + load() · โยน LossyCarrierError ถ้า tier ไม่ผ่าน"""
```

> **เหตุผลที่ไม่เชื่อนามสกุลไฟล์:** ผู้ใช้เปลี่ยนชื่อไฟล์ได้ และไฟล์ต้องสงสัยอาจถูกตั้งชื่อให้เข้าใจผิดโดยเจตนา การเชื่อนามสกุลคือ type confusion vulnerability แบบคลาสสิก

**พึ่งพา:** `domain`, `common`
**ถูกพึ่งพาโดย:** `pipeline`, `analyzer`, `research`

---

### 4.3 `domain/` — ตัวแทนข้อมูลกลาง

**หน้าที่:** นิยามภาษากลางที่ทำให้ชั้นล่างไม่ต้องรู้จัก format
แพ็กเกจนี้ **เล็กที่สุดแต่สำคัญที่สุด** — ถ้า `Plane` ออกแบบผิด ทุกชั้นที่อยู่ใต้มันจะพังตาม

```python
# plane.py
@dataclass
class Plane:
    values: np.ndarray        # int16 (DCT coeff) หรือ uint8 (spatial)
    changeable: np.ndarray    # bool, shape เดียวกับ values
    meta: dict[str, Any]      # qtable, component_id, block_grid, subsampling

    def flatten(self) -> tuple[np.ndarray, np.ndarray]:
        """คืน (values 1-D, index กลับตำแหน่งเดิม) เฉพาะตัวที่ changeable"""
    def unflatten(self, flat: np.ndarray, index: np.ndarray) -> None: ...
    def n_changeable(self) -> int: ...
    def copy(self) -> Plane: ...
```

```python
# selection.py
def build_changeable_mask(values, domain: str, *, skip_dc: bool = True) -> np.ndarray:
    """DCT: nonzero AC เท่านั้น (DC และ zero AC = wet) · spatial: ทั้งหมด"""

def permute(n: int, seed: bytes) -> np.ndarray:
    """ลำดับลับของการไล่ coefficient — ChaCha20-based Fisher-Yates"""

def inverse_permute(order: np.ndarray) -> np.ndarray: ...
```

```python
# capacity.py
def bits_from_bpnzac(rate: float, nnz_ac: int) -> int: ...
def bpnzac_from_bits(bits: int, nnz_ac: int) -> float: ...
def max_payload_bits(plane: Plane, *, stc_height: int) -> int:
    """เพดานจริงหลังหัก overhead ของ STC และ header"""
```

> **ทำไมต้อง `skip_dc=True`:** การแก้ DC coefficient เปลี่ยนความสว่างเฉลี่ยของทั้งบล็อก 8×8 ซึ่งเห็นด้วยตาเปล่าและตรวจเจอง่ายมาก งานวิจัยมาตรฐานทั้งหมดฝังเฉพาะ non-zero AC — และนั่นคือที่มาของหน่วย **bpnzAC** (bits per non-zero AC coefficient) ที่ใช้รายงานผล

**พึ่งพา:** `common` เท่านั้น
**ถูกพึ่งพาโดย:** `carrier`, `cost`, `coder`, `pipeline`, `analyzer`, `research`

---

### 4.4 `cost/` — Distortion Model

**หน้าที่:** ตอบคำถามเดียว — "ถ้าจะแก้ค่าตัวนี้ +1 หรือ −1 จะเสี่ยงถูกตรวจเจอเท่าไหร่"
ยิ่งค่า cost ต่ำ ยิ่งเป็นตำแหน่งที่ปลอดภัย (ขอบภาพ, พื้นผิวซับซ้อน) ยิ่งสูงยิ่งอันตราย (พื้นเรียบ, ท้องฟ้า)

```python
# base.py
class CostModel(ABC):
    name: ClassVar[str]
    domains: ClassVar[tuple[str, ...]]
    requires_precover: ClassVar[bool] = False

    @abstractmethod
    def costs(self, carrier: Carrier, plane: Plane) -> tuple[np.ndarray, np.ndarray]:
        """คืน (rho_plus1, rho_minus1) shape เดียวกับ plane.values
        ตำแหน่งที่แก้ไม่ได้ต้องเป็น np.inf (wet)"""
```

| ไฟล์ | คลาส | domain | ใช้เมื่อไหร่ | Status |
|---|---|---|---|:---:|
| `juniward.py` | `JUniwardCost` | dct | **ค่าเริ่มต้นสำหรับ JPEG** | `N` |
| `si_uniward.py` | `SiUniwardCost` | dct | มีภาพต้นฉบับก่อนบีบอัด — ปลอดภัยกว่าชัดเจน | `N` |
| `uerd.py` | `UerdCost` | dct | baseline ที่เร็วกว่า ใช้เทียบผล | `N` |
| `hill.py` | `HillCost` | spatial | PNG | `N` |
| `wavelet.py` | `daubechies8_filters()`, `dwt2_directional()` | — | ใช้ร่วมกันระหว่าง juniward/si | `N` |
| `legacy_texture.py` | `LegacyTextureCost` | spatial | gradient+entropy ของ LSB-PP เดิม เก็บไว้เทียบ | `R` |

```python
# juniward.py
class JUniwardCost(CostModel):
    name = "j-uniward"
    domains = ("dct",)
    SIGMA: float = 2 ** -6          # ค่าคงที่กันหารศูนย์ ตามเปเปอร์ต้นฉบับ
    WET_COST: float = 1e13

    def costs(self, carrier, plane) -> tuple[np.ndarray, np.ndarray]: ...
    def _spatial_impact(self, qtable: np.ndarray) -> np.ndarray:
        """ผลของการแก้ coeff 1 หน่วย ที่แผ่ไปยัง pixel ในบล็อก"""
    def _wavelet_residual(self, spatial: np.ndarray) -> tuple[np.ndarray, ...]: ...
```

> **ข้อควรระวังเชิงความปลอดภัย:** `costs()` ต้องขึ้นกับ **cover เท่านั้น** ห้ามขึ้นกับ payload หรือคีย์ใดๆ ถ้า cost ขึ้นกับข้อมูลลับ การกระจายตัวของการเปลี่ยนแปลงจะรั่วข้อมูลออกมาเป็น side channel

**พึ่งพา:** `domain`, `common`, `numpy`, `scipy`
**ถูกพึ่งพาโดย:** `pipeline/engines`, `research`

---

### 4.5 `coder/` — Syndrome Coding

**หน้าที่:** รับ (cost vector, bit ที่ต้องฝัง) แล้วตอบว่า "แก้ตัวไหนบ้าง" โดยให้ distortion รวมต่ำสุด
ชั้นนี้ไม่รู้จัก format และไม่รู้จัก crypto — เห็นแค่ array กับ bit string

```python
# stc.py
class CapacityError(Exception):
    """payload เกินความจุที่ h นี้รองรับ — แนบ max_bits และ max_bpnzac มาด้วย"""

H_HAT: dict[int, list[int]]     # ตาราง submatrix ตาม constraint height

def embed(
    values:  np.ndarray,        # int16/uint8 1-D เฉพาะตัวที่ changeable
    rho_p1:  np.ndarray,
    rho_m1:  np.ndarray,
    bits:    np.ndarray,        # uint8 0/1
    h:       int = 10,
) -> np.ndarray:
    """คืน values ใหม่ · โยน CapacityError ถ้าฝังไม่ลง"""

def extract(values: np.ndarray, n_bits: int, h: int = 10) -> np.ndarray:
    """คืน bit array — เป็นแค่การคูณเมทริกซ์ เร็วกว่า embed มาก"""
```

```python
# simulator.py
def simulate_embedding(rho_p1, rho_m1, alpha: float) -> np.ndarray:
    """optimal coder simulation: คืนความน่าจะเป็นการเปลี่ยนแปลงต่อตำแหน่ง
    ใช้ใน research เพื่อวัด 'ขีดจำกัดทางทฤษฎี' แยกจากประสิทธิภาพของ STC จริง"""

def lambda_from_payload(rho_p1, rho_m1, target_bits: int) -> float:
    """binary search หา lambda ที่ทำให้ ternary entropy = target"""
```

| ไฟล์ | หน้าที่ | Status |
|---|---|:---:|
| `stc.py` | Viterbi trellis encoder/decoder | `N` |
| `simulator.py` | ขีดจำกัดเชิงทฤษฎี ใช้เทียบกับ STC จริง | `N` |
| `opap.py` | OPAP ของ LSB-PP เดิม (ย้ายมาจาก `lsb_pp.py`) | `R` |
| `_native/stc_kernel.c` | Viterbi ภาษา C | `N` |
| `_native/build.py` | cffi builder + fallback ไป numpy ถ้า build ไม่ได้ | `N` |

> **ทำไมต้องเป็น C:** Viterbi ที่ h=10 คือ 1024 state ต่อ 1 bit บนภาพ 512×512 ที่ 0.4 bpnzAC มี bit หลายหมื่นตัว → numpy loop ใช้เวลาระดับนาที ส่วน C ใช้ระดับวินาที ตัว Python fallback ควรมีไว้ให้ import ได้ แต่ต้อง warn ชัดเจนว่าช้า

**พึ่งพา:** `domain`, `common`, `numpy`
**ถูกพึ่งพาโดย:** `pipeline/engines`, `research`

---

### 4.6 `crypto/` — ความลับและการพิสูจน์ตัวตน

**หน้าที่:** ผลิต bit stream ที่แยกจากค่าสุ่มไม่ออก และรับประกันว่าถ้าถูกแก้ไขจะรู้
**ชั้นนี้ต้อง audit ได้แบบแยกเดี่ยว** — ห้าม import อะไรจาก `sieng` ยกเว้น `common`

#### `kem/` — Key Encapsulation

```python
# x25519.py / mlkem768.py มี interface เดียวกัน
def generate_keypair() -> tuple[bytes, bytes]:              # (sk, pk)
def encapsulate(pk: bytes) -> tuple[bytes, bytes]:          # (ct, ss)
def decapsulate(sk: bytes, ct: bytes) -> bytes:             # ss
```

```python
# hybrid.py
@dataclass(frozen=True)
class HybridPublicKey:
    x25519_pk: bytes      # 32 B
    mlkem_pk:  bytes      # 1184 B

class HybridKem:
    SUITE_ID = b"sieng3/kem/x25519-mlkem768/v1"

    @staticmethod
    def encapsulate(pk: HybridPublicKey) -> tuple[bytes, bytes]:
        """คืน (ciphertext_bundle, shared_secret 32 B)

        ss = HKDF-Extract-Expand(
            IKM  = ss_x25519 ‖ ss_mlkem ‖ ct_mlkem ‖ ct_x25519 ‖ pk_x25519 ‖ pk_mlkem,
            info = SUITE_ID)

        ★ ct และ pk ต้องอยู่ใน transcript ด้วย ไม่ใช่แค่ ss สองก้อน
          เพราะ ML-KEM ไม่ committing โดยตัวมันเอง
        """

    @staticmethod
    def decapsulate(sk_bundle, ct_bundle) -> bytes: ...
```

#### `auth/` — Identity & Key Binding ★ P0

แพ็กเกจนี้คือคำตอบของช่องโหว่ MITM ที่ hybrid KEM เพียงอย่างเดียวแก้ไม่ได้ (ดู §2.7)

```python
# identity.py
@dataclass(frozen=True)
class Identity:
    """ตัวตนถาวรของผู้ใช้หนึ่งคน — สร้างครั้งเดียว ใช้ตลอด"""
    x25519_static_pk: bytes      # 32 B  ใช้ทำ AUTH_IMPLICIT
    mlkem_static_pk:  bytes      # 1184 B
    ed25519_pk:       bytes      # 32 B  ใช้ทำ AUTH_PQ_EXPLICIT
    mldsa_pk:         bytes      # 1952 B

    def fingerprint(self) -> str:
        """SHA-256 ของ bundle → แสดงเป็นกลุ่มตัวอักษรให้ผู้ใช้เทียบด้วยตา
           ★ นี่คือจุดที่ trust เริ่มต้นจริง ไม่มีทางลัด"""

def generate_identity() -> tuple[IdentitySecret, Identity]: ...
```

```python
# transcript.py
def build(
    sender: Identity, recipient: Identity,
    eph_pk: bytes, mlkem_ct: bytes,
    suite: int, version: int, sid: bytes,
) -> bytes:
    """ต่อทุกฟิลด์ตามลำดับตายตัวพร้อม length prefix ทุกชิ้น

    ★ ต้องใช้ length-prefix ไม่ใช่ concat เฉยๆ ไม่งั้นเกิด canonicalization
      attack: (A‖BC) กับ (AB‖C) จะได้ transcript เดียวกัน
    """
```

```python
# key_binding.py
AUTH_IMPLICIT = 0x01      # overhead 0 B — ค่าเริ่มต้น
AUTH_PQ_EXPLICIT = 0x02   # overhead 3,373 B — เมื่อ envelope เป็น external

def derive_authenticated_secret(
    mode: int,
    sender_sk: IdentitySecret,
    recipient: Identity,
    eph_sk: bytes,
    transcript: bytes,
) -> bytes:
    """AUTH_IMPLICIT (HPKE auth mode):
         ss = HKDF( DH(eph_sk, r.x25519) ‖ DH(static_sk, r.x25519)
                  ‖ mlkem_ss ‖ transcript, info=SUITE_ID )
       คนที่ไม่มี static private key ของผู้ส่งคำนวณ ss ไม่ได้
       → ได้ sender authentication โดยไม่เสีย byte เพิ่มเลย"""
```

```python
# signatures.py
def sign_transcript(sk: IdentitySecret, transcript: bytes) -> bytes:
    """Ed25519 ‖ ML-DSA-65 — ลงนามทั้งคู่ ต้องผ่านทั้งคู่จึงนับว่าถูก"""
def verify_transcript(identity: Identity, transcript: bytes, sig: bytes) -> bool: ...
```

```python
# trust_store.py
class TrustStore:
    def add(self, identity: Identity, *, verified_via: str) -> None:
        """verified_via = 'fingerprint' | 'qr' | 'manual' — บันทึกว่าเชื่อเพราะอะไร"""
    def get(self, fingerprint: str) -> Identity | None: ...
    def revoke(self, fingerprint: str, reason: str) -> None: ...
    def is_revoked(self, fingerprint: str) -> bool: ...
```

> **จุดที่ไม่มีเทคโนโลยีไหนช่วยได้:** การเชื่อ identity ครั้งแรกต้องเกิดนอกระบบเสมอ — ผู้ใช้สองคนต้องเทียบ fingerprint กันผ่านช่องทางที่เชื่อได้ (เจอตัว โทรหากัน สแกน QR) ถ้าข้ามขั้นนี้ authentication ทั้งหมดที่สร้างมาไม่มีความหมาย GUI ต้องบังคับให้เกิดขั้นตอนนี้ ไม่ใช่ทำเป็น dialog ที่กด "ตกลง" ผ่านได้

#### `envelope.py` ★ P0

```python
ENVELOPE_EXTERNAL  = 0   # ค่าเริ่มต้น — .sess file แยก · per-image = header เท่านั้น
ENVELOPE_INLINE    = 1   # ฝังในภาพ — ต้อง capacity ≥ 8 × envelope_size
ENVELOPE_MULTIPART = 2   # กระจายในไฟล์แรกๆ ของ session

@dataclass
class SessionEnvelope:
    version: int
    suite:   int
    sid:     bytes                 # 4 B
    sender_fingerprint: bytes      # 32 B
    eph_x25519_pk: bytes           # 32 B
    mlkem_ct:      bytes           # 1088 B
    auth_mode:     int
    signature:     bytes | None    # 3373 B เมื่อ AUTH_PQ_EXPLICIT

    def pack(self) -> bytes: ...
    def size(self) -> int: ...

def choose_mode(carrier: Carrier, payload_rate: float,
                auth_mode: int) -> int:
    """เลือกโหมดจากความจุจริง — ดูตัวเลขใน §2.7.2
       512×512 QF75 ที่ 0.1 bpnzAC มีที่ ~325 B แต่ envelope ขั้นต่ำ ~1.2 KB
       → บังคับเป็น EXTERNAL โดยอัตโนมัติ พร้อม log เหตุผล"""
```

#### `kdf/`

```python
# hkdf.py
def extract(salt: bytes, ikm: bytes) -> bytes:              # PRK 32 B
def expand(prk: bytes, info: bytes, length: int) -> bytes:  # OKM
def derive(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
```

```python
# labels.py — domain separation string ทั้งหมดรวมไว้ที่เดียว
KEM_SUITE     = b"sieng3/kem/v1"
CHAIN_INIT    = b"sieng3/chain/v1"
RATCHET_STEP  = b"sieng3/ratchet/v1"
MESSAGE_KEY   = b"sieng3/msg/v1"
HEADER_KEY    = b"sieng3/hdrkey/v1"     # ★ derive จาก ss ไม่ใช่จาก MK[n]
KEYSTORE_WRAP = b"sieng3/keystore/v1"
```

> **ทำไม `HEADER_KEY` ต้อง derive จาก `ss` โดยตรง:** header บรรจุ `ctr` แต่การจะหา `MK[ctr]` ได้ต้องรู้ `ctr` ก่อน — เป็นวงจรไก่กับไข่ ผู้รับมี `ss` อยู่แล้วตั้งแต่ทำ KEM เสร็จ จึงถอด header ได้ทันทีแล้วค่อย ratchet ตามไป

#### `aead/gcm_siv.py`

```python
def seal(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes: ...
def open_(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """โยน DecryptError เดียวเสมอ ไม่แยกสาเหตุ ไม่ให้ timing ต่างกัน"""
```

#### `ratchet/`

```python
# chain.py
@dataclass
class MessageKeys:
    aead:     bytes   # 32 B
    nonce:    bytes   # 12 B
    hdr:      bytes   # 32 B
    seed_sel: bytes   # 32 B  ← selection channel ของ STC
    counter:  int

class SendChain:
    def __init__(self, ss: bytes, sid: bytes) -> None: ...
    def next_message_keys(self) -> MessageKeys:
        """MK[n] = HKDF(CK[n], MESSAGE_KEY)
           CK[n+1] = HKDF(CK[n], RATCHET_STEP)  แล้ว zeroize CK[n] ทันที"""

class RecvChain:
    def keys_for(self, counter: int) -> MessageKeys:
        """ratchet ไปข้างหน้าถึง counter · เก็บคีย์ที่ข้ามใน skipped pool
           โยน RatchetLimitError ถ้าเกิน settings.max_ratchet_skip"""
    def mark_consumed(self, counter: int) -> None:
        """กัน replay — counter ที่เคยใช้แล้วใช้ซ้ำไม่ได้"""
```

```python
# state_store.py
class StateStore:
    def save(self, state: ChainState) -> None:
        """เข้ารหัสด้วย AEAD แล้วเขียนแบบ write-temp → fsync → rename
           ★ ต้องเรียกก่อนเขียนไฟล์ stego เสมอ ยอมข้าม counter ดีกว่าใช้ซ้ำ"""
    def load(self) -> ChainState: ...
```

```python
# state_lock.py  ★ P0
class StateLock:
    def __enter__(self) -> StateLock:
        """exclusive lock ข้าม process และข้าม OS (portalocker)
           ★ ต้องล็อกก่อน load ไม่ใช่ก่อน save — ไม่งั้นสอง process
             อ่าน counter เดียวกันแล้วเขียนทับกัน"""
    def __exit__(self, *exc) -> None: ...
```

```python
# generation.py  ★ P0
@dataclass(frozen=True)
class Generation:
    value: int          # เพิ่มขึ้นอย่างเดียว ไม่มีวันลด
    machine_id: bytes   # ตรวจว่า state ถูกคัดลอกข้ามเครื่อง

def next_generation(current: Generation) -> Generation: ...
```

```python
# rollback_guard.py  ★ P0
class RollbackDetected(CryptoError): ...

def verify_monotonic(loaded: ChainState, last_seen: Generation) -> None:
    """โยน RollbackDetected ถ้า generation ลดลงหรือ machine_id ไม่ตรง

    ★ ข้อจำกัดที่ต้องบันทึกใน docstring:
      ตรวจจับได้ ไม่ได้ป้องกัน — ผู้โจมตีที่เขียนไฟล์ได้ย้อนได้เสมอ
      ชั้นป้องกันจริงคือ monotonic counter ระดับ OS (Phase 2)
      และ AES-GCM-SIV ที่ทำให้ nonce ซ้ำไม่ล่มสลาย (ดู §2.8.2)"""

def on_rollback(policy: str) -> None:
    """policy = 'abort' (ค่าเริ่มต้น) | 'rekey' | 'warn'
       'warn' ต้องเปิดใช้แบบตั้งใจเท่านั้น และต้องขึ้นเตือนใน UI ทุกครั้ง"""
```

#### `lifecycle/` ★ P1

วงจรชีวิตเดียวกันบังคับใช้กับคีย์ทุกชนิด ไม่มีข้อยกเว้น

```
generate → store → load → use → rotate → revoke → destroy
```

| คีย์ | อายุ | เก็บที่ไหน | rotate เมื่อไหร่ | revoke ได้ไหม |
|---|---|---|---|:---:|
| Identity signing key (Ed25519 + ML-DSA) | ถาวร | keystore (Argon2id + AEAD) | ปีละครั้ง หรือเมื่อสงสัยว่าหลุด | ได้ |
| Identity static KEM key | ถาวร | keystore | ปีละครั้ง | ได้ |
| Ephemeral X25519 | 1 session | RAM | ทุก session | ไม่ต้อง |
| ML-KEM shared secret | 1 session | RAM | ทุก session | ไม่ต้อง |
| Chain key `CK[n]` | 1 ข้อความ | state file (เข้ารหัส) | ทุกข้อความ | ไม่ต้อง |
| Message key `MK[n]` | 1 ข้อความ | RAM | ทุกข้อความ | ไม่ต้อง |
| `seed_sel` / `K_hdr` | 1 ข้อความ | RAM | ทุกข้อความ | ไม่ต้อง |
| Password-derived key | ต่อการใช้งาน | ไม่เก็บ | — | — |

```python
# key_state.py
class KeyState(Enum):
    GENERATED = auto(); ACTIVE = auto(); ROTATING = auto()
    REVOKED = auto();   DESTROYED = auto()

class ManagedKey:
    def transition(self, to: KeyState) -> None:
        """บังคับ state machine — ใช้คีย์ที่ REVOKED/DESTROYED ต้องโยน error"""
```

```python
# destroy.py
def destroy_session(sid: bytes) -> DestroyReport:
    """ลบ state file + skipped key pool + cache ทั้งหมดของ session
       คืน report ว่าลบอะไรไปบ้าง เพื่อให้ผู้ใช้ตรวจสอบได้"""
```

> **ข้อความที่ต้องอยู่ใน `zeroize.py` และ `THREAT_MODEL.md`:** Python ไม่รับประกันการล้างหน่วยความจำ — `bytes` เป็น immutable, GC อาจทิ้งสำเนาไว้, และ OS อาจ swap ลงดิสก์ `zeroize()` ทำได้ดีที่สุดเท่าที่ภาษาอนุญาต **การป้องกัน memory compromise อยู่นอกขอบเขตของ Phase 1 และต้องประกาศไว้ ไม่ใช่ปล่อยให้ผู้ใช้เข้าใจเอาเอง**

#### `header.py`

```python
HEADER_LEN_COMPACT = 12
HEADER_LEN_BOUND   = 16

@dataclass(frozen=True)
class Header:
    version: int      # 4 bit
    suite:   int      # 4 bit
    sid:     int      # 32 bit  session id
    counter: int      # 24 bit
    length:  int      # 24 bit  ความยาว ciphertext
    flags:   int      # 8 bit

    def pack(self) -> bytes: ...
    @classmethod
    def unpack(cls, raw: bytes) -> Header: ...

def whiten(raw: bytes, k_hdr_session: bytes, ctr_hint: int = 0) -> bytes:
    """XOR ด้วย keystream — ผลลัพธ์ต้องผ่าน randomness test"""
def unwhiten(raw: bytes, k_hdr_session: bytes) -> bytes: ...
```

#### ไฟล์ที่เหลือ

| ไฟล์ | API หลัก | หมายเหตุ | Status |
|---|---|---|:---:|
| `kdf/argon2.py` | `derive_key(password, salt) -> bytes` | ย้ายจาก `sym_encrypt.py` · RFC 9106 t=3 m=64MiB p=4 | `R` |
| `keystore.py` | `save_private_key()`, `load_private_key()` | private key ต้อง wrap ด้วย Argon2id + AEAD เสมอ | `N!` |
| `zeroize.py` | `zeroize(buf: bytearray)`, `SecretBytes` (context manager) | Python ล้าง memory ได้ไม่สมบูรณ์ — บันทึกข้อจำกัดไว้ใน docstring | `N!` |
| `session.py` | `Session.initiator()`, `Session.responder()`, `Session.from_password()` | รวม KEM + chain เข้าด้วยกัน | `N!` |

**พึ่งพา:** `common`, `cryptography` (และ `liboqs` ถ้าจำเป็น)
**ถูกพึ่งพาโดย:** `pipeline` เท่านั้น — GUI ห้ามแตะโดยตรง

---

### 4.7 `pipeline/` — Orchestration

**หน้าที่:** ประกอบชั้นล่างทั้งหมดเป็นงานที่ผู้ใช้สั่งได้ จัดการลำดับ ความผิดพลาด และ progress
เป็นชั้นเดียวที่ "เห็นภาพรวม" ทั้งระบบ

```python
# engines/base.py
class Engine(ABC):
    engine_id: ClassVar[str]
    supported_domains: ClassVar[tuple[str, ...]]
    requires_key: ClassVar[bool] = True

    @abstractmethod
    def embed(self, req: EmbedRequest, ctx: RunContext) -> EmbedResult: ...
    @abstractmethod
    def extract(self, req: ExtractRequest, ctx: RunContext) -> ExtractResult: ...
    def estimate_capacity(self, carrier: Carrier) -> CapacityReport: ...
```

```python
# registry.py
class EngineRegistry:
    def register(self, engine: type[Engine]) -> None: ...
    def resolve(self, engine_id: str, domain: str) -> type[Engine]:
        """โยน IncompatibleEngineError ถ้า engine ใช้กับ domain นี้ไม่ได้
           ★ แทนที่ if/elif ใน config_mode.py เดิมทั้งหมด"""
    def for_domain(self, domain: str) -> list[type[Engine]]:
        """GUI ใช้ตัวนี้สร้าง dropdown — ไม่ hardcode รายชื่อใน UI"""
```

```python
# embed.py
@dataclass
class EmbedRequest:
    cover_path:   Path
    payload:      bytes | Path
    engine_id:    str
    payload_rate: float | None = None      # bpnzAC · None = auto
    precover_path: Path | None = None      # สำหรับ SI-UNIWARD
    recipient_pk: HybridPublicKey | None = None
    password:     str | None = None
    stc_height:   int = 10
    output_path:  Path | None = None

@dataclass
class EmbedResult:
    output_path:    Path
    bits_embedded:  int
    achieved_bpnzac: float
    changes_made:   int
    psnr:           float | None
    engine_id:      str
    duration_ms:    int

def run_embed(req: EmbedRequest, ctx: RunContext) -> EmbedResult: ...
```

| ไฟล์ | หน้าที่ | Status |
|---|---|:---:|
| `embed.py` | `run_embed()` — ลำดับตามหัวข้อ 2.3 | `R` |
| `extract.py` | `run_extract()` — ลำดับตามหัวข้อ 2.4 | `R` |
| `registry.py` | `EngineRegistry` | `N` |
| `context.py` | `RunContext(progress, logger, cancel_token)` | `N` |
| `engines/juniward_stc.py` | `JUniwardStcEngine` — engine หลักตัวใหม่ | `N` |
| `engines/hill_stc.py` | `HillStcEngine` | `N` |
| `engines/lsbpp.py` | `LsbppEngine` — ห่อโค้ดเดิม | `R` |
| `engines/locomotive.py` | `LocomotiveEngine` — ฝังกระจายหลายไฟล์ · `supported_domains = ("dct", "spatial")` | `R` |
| `engines/metadata.py` | `MetadataEngine` — PNG iTXt / JPEG APPn (ตัดส่วน MP3 ID3 ออก) | `R` |
| `yaml/schema.py` | `PipelineConfig`, `StepConfig`, `RefExpr` | `N` |
| `yaml/loader.py` | `load_pipeline(path) -> PipelineConfig` | `R` |
| `yaml/validate.py` | `validate(config) -> list[Issue]` | `R` |
| `yaml/templates/` | เทมเพลต 01–05 เดิม | `E` |

> **จุดที่ต้องรื้อหนักที่สุด:** `config_mode.py` เดิมยาวและรวมทุกอย่าง — resolve reference, ตรวจ type, dispatch, route output, สร้าง extract pipeline ย้อนกลับ ต้องแยกเป็น `schema` (นิยาม) / `validate` (ตรวจ) / `embed`+`extract` (รัน) / `registry` (เลือก engine) และเขียน test ครอบก่อนแตะ ไม่งั้น pipeline 5 เทมเพลตจะพังเงียบๆ

**พึ่งพา:** `carrier`, `domain`, `cost`, `coder`, `crypto`, `common`
**ถูกพึ่งพาโดย:** `ui`, `research`

---

### 4.8 `analyzer/` — ฝั่งตรวจจับ

**หน้าที่:** วิเคราะห์ไฟล์ต้องสงสัย — เป็นระบบที่แยกอิสระจากฝั่งฝัง มีวงจรชีวิตของตัวเอง
ส่วนใหญ่เป็นโค้ดที่มีอยู่แล้วและใช้ได้ดี ย้ายตำแหน่งเป็นหลัก

```python
# dispatcher.py  (เดิม handle.py)
class FileAnalyzerDispatcher:
    def analyze_file(self, file_path: str) -> dict[str, Any]:
        """เลือก handler ตามชนิดไฟล์ แล้วรวมผลเป็น report เดียว"""

def analyze(file_path: str) -> dict[str, Any]: ...
```

```python
# formats/base_handler.py
class BaseFormatHandler(ABC):
    _entropy_reliable: ClassVar[bool] = False
    # ★ entropy บอกอะไรได้เฉพาะบนพาหะที่ยังไม่ถูกบีบอัด
    #   บน PNG/JPEG ทั้งไฟล์ ~1.0 อยู่แล้ว จะเกิด false positive

    def analyze_metadata(self) -> dict[str, Any]: ...
    def extract_raw_structure(self) -> dict[str, Any]:
        """รัน hachoir + binwalk + entropy scan ขนานกันบน thread pool
           พร้อมตรวจ overlay จาก content_end ที่ format ประกาศเอง"""
    def _integrity_report(self, raw: bytes) -> dict[str, Any]:
        """override ต่อ format — PNG ตรวจ CRC, RIFF ตรวจ JUNK chunk"""
    def add_mediainfo(self, structure_results: dict) -> None: ...
    @abstractmethod
    def analyze(self) -> dict[str, Any]: ...
```

| กลุ่ม | ไฟล์ | API หลัก | Status |
|---|---|---|:---:|
| Dispatch | `dispatcher.py` | `FileAnalyzerDispatcher.analyze_file()` | `E` |
| Compare | `compare.py` | `compare_results()`, `compare_metadata()`, `compare_structure()`, `compare_statistics()` | `E` |
| Sandbox | `docker_bridge.py` | `analyze()`, `zsteg_scan()`, `zsteg_extract()`, `carve()` | `E` |
| Format | `formats/png_handler.py` | `PNGHandler._integrity_report()`, `_tag_suspicious_chunks()` | `E` |
| Format | `formats/wav_handler.py` / `avi_handler.py` | RIFF integrity + mediainfo | `E` |
| Format | **`formats/jpeg_handler.py`** | `JpegHandler` — ★ ยังไม่มี ต้องเขียน | `N` |
| Stat | `modules/stat/base.py` | `BaseAttack.analyze_blind(data) -> dict` | `E` |
| Stat | `modules/stat/{chi_square,rs_analysis,ws,sample_pairs,pdh,hcf_com}.py` | attack ละตัว | `E` |
| DCT | **`modules/dct/double_compression.py`** | ตรวจร่องรอยการบีบอัดซ้ำจาก histogram ของ coeff | `N` |
| DCT | **`modules/dct/qtable_fingerprint.py`** | เทียบ quant table กับฐานข้อมูลกล้อง/ซอฟต์แวร์ | `N` |
| DCT | **`modules/dct/blockiness.py`** | วัดความไม่ต่อเนื่องที่ขอบบล็อก 8×8 | `N` |
| Tools | `external_tools/*.py` | wrapper ของ binwalk/exiftool/hachoir/mediainfo/pngcheck/zsteg | `E` |
| Sandbox | **`sandbox.py`** | `run_sandboxed(tool, path, profile) -> Result` | `N` |
| Sandbox | **`resource_policy.py`** | `Profile` ต่อเครื่องมือ — CPU/RAM/PID/timeout | `N` |
| Sandbox | **`limits.py`** | เพดาน input **ก่อน** ส่งเข้า parser | `N` |
| Sandbox | **`timeout.py`** | watchdog + kill ทั้ง process tree | `N` |

> **สโคปของ analyzer กว้างกว่าสโคปของ carrier โดยเจตนา**
> `carrier/` รองรับแค่ jpg/png เพราะเป็นสองไฟล์ที่เรา **ฝัง** ได้อย่างปลอดภัย แต่ `analyzer/` ยังคงรองรับ wav/avi ต่อไป เพราะหน้าที่ของมันคือ **ตรวจไฟล์ที่คนอื่นส่งมา** ซึ่งเราไม่ได้เลือกว่าจะเป็นชนิดไหน
> โค้ดส่วนนี้มีอยู่แล้วและทำงานได้ดี (`E` ทั้งหมด) การตัดออกจะเสียความสามารถโดยไม่ได้ลดความเสี่ยงอะไร — parser พวกนี้รันใน container ที่จำกัดทรัพยากรอยู่แล้ว
> **สิ่งที่ต้องระวังคือ UI:** ต้องไม่ทำให้ผู้ใช้เข้าใจว่า "วิเคราะห์ .wav ได้ = ฝังใน .wav ได้" หน้า analyzer กับหน้า embed ต้องมีรายการนามสกุลที่รองรับคนละชุดและแสดงให้ชัด

#### Sandbox hardening ★ P1

Docker เพียงอย่างเดียวกัน RCE ได้ระดับหนึ่ง แต่ **ไม่กันการใช้ทรัพยากรจนหมดเครื่อง** ต้องกำหนดขอบเขตให้ครบ

| Control | ค่าที่บังคับ | กันอะไร |
|---|---|---|
| `--network none` | ไม่มี network เลย | exfiltration, C2 callback |
| `--read-only` + `--tmpfs /tmp:size=64m` | FS อ่านอย่างเดียว, tmp มีโควตา | เขียนทับไฟล์, เติม disk จนเต็ม |
| `--memory 512m --memory-swap 512m` | RAM จำกัด ไม่ให้ swap | decompression bomb, memory exhaustion |
| `--cpus 1.0` | 1 core | CPU exhaustion, infinite parser loop |
| `--pids-limit 128` | จำกัดจำนวน process | fork bomb |
| `--security-opt no-new-privileges` | ห้ามยกสิทธิ์ | privilege escalation |
| `--cap-drop ALL` | ตัด capability ทั้งหมด | หลายอย่างพร้อมกัน |
| `--user 65534:65534` | รันเป็น nobody | ความเสียหายเมื่อหลุด container |
| timeout 60 s (kill −9 ที่ 75 s) | เวลาสูงสุดต่อเครื่องมือ | hang |
| ไม่ mount docker socket | — | container escape ที่ง่ายที่สุด |

**เพดาน input ที่ต้องเช็กก่อนถึง parser** (ใน `limits.py` — ถูกกว่าปล่อยให้ container ตาย)

| ตรวจ | เพดานเริ่มต้น | กันอะไร |
|---|---:|---|
| ขนาดไฟล์ | 256 MB | ไฟล์ยักษ์ |
| ความกว้าง × สูง | 100 MPixel | decompression bomb |
| อัตราขยายหลังคลาย | 100× | zip bomb / JPEG bomb |
| ความลึกของ container ซ้อน | 4 ชั้น | recursive container |
| จำนวน EXIF entry | 10,000 | malformed EXIF ที่ทำให้ parser ค้าง |
| จำนวน JPEG marker | 4,096 | marker flooding |

> **ความจริงที่ต้องยอมรับเรื่อง fuzzing:** ช่องโหว่ระดับ memory corruption ไม่ได้อยู่ในโค้ด Python ของเรา แต่อยู่ใน **libjpeg-turbo ที่ `carrier/image/jpeg.py` เรียกผ่าน binding** — `atheris` ทดสอบชั้น Python ได้ แต่จะไม่พบ heap overflow ในชั้น C การครอบคลุมจริงต้องใช้ libFuzzer/AFL++ ที่ระดับ C ซึ่งควรบันทึกเป็น known gap ของ Phase 1 แล้วชดเชยด้วย sandbox ที่แน่นตามตารางข้างบน

**พึ่งพา:** `carrier`, `domain`, `common`, Docker
**ถูกพึ่งพาโดย:** `ui/gui/pages/analyzer_page.py`, `ui/cli`, `research`

---

### 4.9 `ui/` — Presentation

**หน้าที่:** รับ input แสดงผล ไม่มี business logic แม้แต่บรรทัดเดียว
ทุกอย่างที่ GUI ทำต้องเรียกผ่าน `pipeline` หรือ `analyzer` เท่านั้น

| กลุ่ม | ไฟล์ | หน้าที่ | Status |
|---|---|---|:---:|
| Shell | `gui/main_window.py` | `MainWindow` — sidebar + stacked page router | `E` |
| Page | `gui/pages/embed_page.py` | เลือกโหมด standalone / configurable | `E` |
| Page | `gui/pages/extract_page.py` | ถอดข้อมูล | `E` |
| Page | `gui/pages/analyzer_page.py` | วิเคราะห์ไฟล์เดี่ยว | `E` |
| Page | `gui/pages/compare_page.py` | เทียบ cover กับ stego | `E` |
| Sub-page | `gui/pages/sub_pages/embed/{standalone,configurable}_page.py` | ฟอร์มของแต่ละโหมด | `E` |
| Tab | `gui/tabs/embed/{lsb,loco,metadata}_embed.py` | UI ต่อ engine | `R` |
| Tab | `gui/tabs/analyzer/{bit_stat,file_structure,metadata_tab,report_tab,zsteg_card}.py` | แสดงผลวิเคราะห์ | `E` |
| Tab | `gui/tabs/compare/{meta,stat,struct}_diff_tab.py` | diff view | `E` |
| Component | `gui/components/worker.py` | QThread wrapper — งานหนักห้ามรันบน UI thread | `E` |
| Component | `gui/components/{files_drop,step_card,toggle_switch,...}.py` | widget ที่ใช้ซ้ำ 14 ตัว | `E` |
| Style | `gui/styles/default.qss` | ธีมมืด | `E` |
| Asset | `gui/assets/{svg,png}/` | ไอคอน 40+ ตัว (มีทั้ง svg และ png ที่ซ้ำกัน) | `E` |
| CLI | `cli/embed.py`, `cli/extract.py`, `cli/analyze.py` | argparse → **typer** | `R` |

> **หนี้ทางเทคนิคที่ควรเก็บกวาด:** `gui/tabs/embed/*.py` แต่ละไฟล์รู้จัก engine ตัวใดตัวหนึ่งแบบตายตัว เมื่อมี `EngineRegistry` แล้ว ควรเปลี่ยนเป็น UI ที่สร้าง form จาก schema ของ engine — เพิ่ม engine ใหม่แล้ว GUI ขึ้นเองโดยไม่ต้องเขียน tab ใหม่
> อีกเรื่อง: `assets/png/` กับ `assets/svg/` มีไอคอนชื่อเดียวกันซ้ำกันเกือบทั้งหมด ควรเหลือ svg อย่างเดียว

**พึ่งพา:** `pipeline`, `analyzer`, `domain`, `common`
**ถูกพึ่งพาโดย:** `main.py` เท่านั้น

---

### 4.10 `common/` — Cross-cutting

```python
# errors.py — exception hierarchy ทั้งระบบ
SiengError
├── CarrierError
│   ├── UnsupportedCarrierError
│   ├── LossyCarrierError
│   └── CorruptCarrierError
├── CapacityError            # payload เกินความจุ
├── CryptoError
│   ├── DecryptError         # ★ ข้อความเดียว ไม่แยกสาเหตุ
│   ├── RatchetLimitError
│   └── ReplayError
├── PipelineError
│   ├── IncompatibleEngineError
│   └── PipelineValidationError
└── ConfigError
```

```python
# logging.py
class RedactingFilter(logging.Filter):
    """★ ตัดค่าที่ดูเหมือนคีย์/nonce/ciphertext ออกจาก log ทุกระดับ
       log ที่มีคีย์หลุดคือช่องโหว่ที่พบบ่อยที่สุดในระบบคริปโต"""

def get_logger(name: str) -> logging.Logger: ...
```

```python
# progress.py
ProgressCallback = Callable[[int, str], None] | None

class ProgressReporter:
    def step(self, percent: int, message: str) -> None: ...
    def scoped(self, lo: int, hi: int) -> ProgressReporter:
        """แบ่งช่วง % ให้ subtask — แก้ปัญหาที่โค้ดเดิมมี update_progress()
           นิยามซ้ำกัน 3 ไฟล์และคำนวณ % ทับกัน"""
```

**พึ่งพา:** stdlib เท่านั้น
**ถูกพึ่งพาโดย:** ทุกโมดูล

---

### 4.11 `research/` — กรอบการวัดผล

**หน้าที่:** ตอบคำถามเดียว — "ที่ทำมาทั้งหมด detector ปัจจุบันจับได้ไหม และจับได้แค่ไหน"
แยก dependency ออกจาก `src/` โดยสมบูรณ์ (torch อยู่ที่นี่เท่านั้น)

| กลุ่ม | ไฟล์ | API หลัก | Status |
|---|---|---|:---:|
| Dataset | `datasets/bossbase.py` | `load_bossbase(root) -> list[Path]`, `verify_hash()` | `N` |
| Dataset | `datasets/alaska2.py` | `load_alaska2(root, quality: int)` | `N` |
| Dataset | `datasets/split.py` | `paired_split(paths, ratio, seed)` — ★ cover/stego ของภาพเดียวกันต้องอยู่ฝั่งเดียวกัน | `N` |
| Feature | `features/dctr.py` | `extract_dctr(jpeg_path) -> np.ndarray` (8000 มิติ) | `N` |
| Feature | `features/gfr.py` | `extract_gfr(jpeg_path) -> np.ndarray` (17000 มิติ) | `N` |
| Classifier | `models/ensemble.py` | `FLDEnsemble.fit/predict` — classifier คู่มาตรฐานของ DCTR/GFR | `N` |
| Deep | `models/srnet/model.py` | `SRNet(nn.Module)` | `N` |
| Deep | `models/srnet/train.py` | `train(cfg)` — curriculum จาก payload สูงไปต่ำ | `N` |
| Dataset | **`datasets/quality.py`** | `build_quality_set(paths, qf)` — สร้างชุด Q50–Q95 จากต้นฉบับเดียวกัน | `N` |
| Dataset | **`datasets/source_meta.py`** | ผูกภาพกับกล้อง/แหล่งที่มา เพื่อทำ cover-source mismatch | `N` |
| Experiment | `experiments/payload_sweep.yaml` | 0.05 / 0.1 / 0.2 / 0.4 bpnzAC × 3 detector × 2 dataset | `N` |
| Experiment | **`experiments/quality_sweep.yaml`** | QF 50/60/70/75/80/90/95 × payload | `N` |
| Experiment | **`experiments/cross_dataset.yaml`** | train BOSS → test ALASKA และย้อนกลับ | `N` |
| Experiment | **`experiments/cover_source_mismatch.yaml`** | train source A → test source B | `N` |
| Metric | `metrics.py` | `p_error(y_true, y_score) -> float`, `roc()`, `md_at_fa()` | `N` |
| Stats | **`stats.py`** | `bootstrap_ci(scores, n=2000)`, `report(p_e, ci, n, seed)` | `N` |

> **กับดักที่ทำให้ผลการทดลองผิดบ่อยที่สุด:** ถ้า cover ของภาพ X อยู่ใน train แต่ stego ของภาพ X อยู่ใน test detector จะเรียนรู้ "ภาพนี้หน้าตายังไง" แทนที่จะเรียนรู้ "ร่องรอยการฝัง" ทำให้ตัวเลขดูดีเกินจริงมาก `paired_split()` มีไว้กันเรื่องนี้โดยเฉพาะ และควรมี test ยืนยัน

#### เกณฑ์ความสมเหตุสมผลของผลการทดลอง ★ P1

การรายงาน `P_E` ตัวเดียวจาก setting เดียวไม่พอที่จะเคลมอะไรได้ ต้องรายงานครบสี่มิติ

| มิติ | ทำอะไร | ตอบคำถามอะไร |
|---|---|---|
| **Payload** | 0.05 / 0.1 / 0.2 / 0.4 bpnzAC | ฝังได้มากแค่ไหนก่อนถูกจับ |
| **JPEG quality** | QF 50 → 95 | quality factor มีผลต่อ detectability แค่ไหน — QF สูงมี coefficient ให้ซ่อนมากขึ้นแต่ noise floor ต่ำลง |
| **Cross-dataset** | train BOSSbase → test ALASKA2 และย้อนกลับ | detector generalize ได้จริงหรือจำ dataset |
| **Cover-source mismatch** | train กล้อง A → test กล้อง B | **สำคัญที่สุด** — ดูด้านล่าง |

**รูปแบบการรายงานที่บังคับ** — ห้ามเขียนแค่ `P_E = 0.47`

```
P_E = 0.47   95% CI [0.44, 0.50]   N = 5,000 pairs
detector = SRNet (seed 42, 3 runs)   dataset = BOSSbase QF75
payload = 0.10 bpnzAC   embedding = J-UNIWARD + STC(h=10)
commit = a1b2c3d   dataset_sha256 = ...
```

ถ้าไม่มี CI และ N ตัวเลขนั้นตีความไม่ได้ — ความต่างระหว่าง 0.47 กับ 0.49 อาจเป็นแค่ noise

> **กับดักที่ทำให้ผลการทดลองผิดบ่อยที่สุด:** ถ้า cover ของภาพ X อยู่ใน train แต่ stego ของภาพ X อยู่ใน test detector จะเรียนรู้ "ภาพนี้หน้าตายังไง" แทนที่จะเรียนรู้ "ร่องรอยการฝัง" ทำให้ตัวเลขดูดีเกินจริงมาก `paired_split()` มีไว้กันเรื่องนี้โดยเฉพาะ และควรมี test ยืนยัน

> **ภัยที่ใหญ่กว่าการเลือก detector ผิด — cover-source mismatch:** BOSSbase เป็นภาพ grayscale ที่ผ่าน pipeline การประมวลผลเดียวกันหมด detector ที่เทรนบนชุดนี้อาจกำลังเรียนรู้ "ลายนิ้วมือของ pipeline" ไม่ใช่ "ร่องรอยการฝัง" ผลที่ได้จะดูดีมากในห้องแล็บและพังทันทีกับภาพจริงจากกล้องหลากหลายรุ่น
> **ในทางกลับกันก็เป็นดาบสองคม:** ตัวเลข `P_E` ที่สวยของเราอาจมาจาก CSM ไม่ใช่จากคุณภาพของการฝัง — การทดสอบ CSM จึงเป็นการตรวจสอบความซื่อสัตย์ของงานตัวเอง ไม่ใช่แค่การทดสอบเพิ่ม

**พึ่งพา:** `carrier`, `cost`, `coder`, `pipeline`, torch
**ถูกพึ่งพาโดย:** ไม่มีอะไรใน `src/` พึ่งพา research (เป็นกฎ)

---

### 4.12 `tests/`

| โฟลเดอร์ | ครอบคลุมอะไร | เกณฑ์ผ่าน | Status |
|---|---|---|:---:|
| `unit/` | ทุกฟังก์ชันสาธารณะ | coverage ≥ 80% ในชั้น 1–5 | `N` |
| `vectors/` | **KAT** — ML-KEM, HKDF-SHA256, AES-GCM-SIV, STC | ตรง reference vector ทุกตัว **แบบ bit ต่อ bit** | `N!` |
| `property/` | `embed(extract(x)) == x` บน jpg/png × ทุก payload rate × ทุก h | hypothesis 500 ตัวอย่างต่อ case | `N` |
| `integration/` | pipeline ครบวงจรรวม YAML 5 เทมเพลต | ผลลัพธ์เหมือนเดิมก่อน/หลัง refactor | `N` |
| `security/` | tamper, สลับ carrier, replay, MITM, rollback, concurrent write, ตรวจ log ไม่มีคีย์ | ทุกเคสต้อง **fail closed** | `N!` |
| `fuzz/` | JPEG, header, envelope, STC, YAML, state file | รัน ≥ 1 ชม./target ต่อ release แล้วไม่มี crash/hang | `N` |
| `fixtures/` | jpg (QF 50/75/95) + png · ภาพเล็ก 64×64 และภาพจริง 512×512 | — | `N` |
| — | **`test_unsupported_carrier_is_refused`** — `.wav` `.mp3` `.bmp` ต้องโยน `UnsupportedCarrierError` ไม่ใช่ crash | ครอบทุกนามสกุลที่ตัดออก | `N` |

**เกณฑ์ของ fuzzing** — malformed input ต้องไม่ทำให้เกิด: crash · hang · memory ระเบิด · secret รั่วออก error message · state ที่ไม่ถูกต้อง · output ที่ผิด
crash ทุกตัวที่เจอต้องถูกเก็บเข้า `tests/fuzz/corpus/` เป็น regression test ถาวร

**Test ที่ต้องมีก่อนอย่างอื่นทั้งหมด (blocking):**

```python
def test_jpeg_roundtrip_is_byte_exact(tmp_path):
    """ถ้า test นี้ไม่ผ่าน ห้ามเขียนโค้ดต่อ"""
    src = FIXTURES / "sample_q75.jpg"
    c = JpegCarrier(src); c.load(); c.save(tmp_path / "out.jpg")
    assert (tmp_path / "out.jpg").read_bytes() == src.read_bytes()
```

```python
def test_header_bits_are_indistinguishable_from_random():
    """header 10,000 ตัวจาก session ต่างกัน ต้องผ่าน monobit + runs test
       และต้องไม่มี byte pattern ซ้ำที่ตำแหน่งใดเลย"""
```

```python
def test_ciphertext_from_other_carrier_is_rejected():
    """ตัด payload จากภาพ A ไปแปะภาพ B → ต้องโยน DecryptError
       (AAD ผูกกับ carrier.fingerprint())"""
```

**Security test ที่เพิ่มจาก P0 — ทุกตัวต้องผ่านก่อน merge**

```python
def test_mitm_key_substitution_is_rejected():
    """ผู้โจมตีสลับ public key ของผู้รับด้วยของตัวเอง
       → AUTH_IMPLICIT ทำให้ ss ไม่ตรง → DecryptError
       → AUTH_PQ_EXPLICIT ทำให้ verify signature ไม่ผ่าน"""

def test_transcript_canonicalization():
    """(A‖BC) กับ (AB‖C) ต้องได้ transcript คนละค่า
       ยืนยันว่ามี length-prefix จริงไม่ใช่ concat เฉยๆ"""

def test_state_rollback_is_detected():
    """สำรอง state → ratchet ไปข้างหน้า → คืนค่ากลับ → ต้องโยน RollbackDetected"""

def test_two_processes_cannot_use_same_counter():
    """spawn 2 process ฝังพร้อมกัน 100 รอบ → counter ต้องไม่ซ้ำเลยแม้แต่ตัวเดียว"""

def test_crash_during_commit_never_reuses_counter():
    """kill -9 ระหว่าง commit ทุกจุดที่เป็นไปได้ → เปิดใหม่แล้ว counter
       ต้องไม่ถอยหลัง (ยอมให้ข้ามได้ ห้ามซ้ำ)"""

def test_revoked_identity_is_refused():
    """identity ที่ถูก revoke แล้ว → สร้าง session ใหม่ไม่ได้"""

def test_envelope_mode_respects_capacity():
    """ภาพ 512x512 ที่ 0.1 bpnzAC → choose_mode() ต้องคืน ENVELOPE_EXTERNAL
       ห้ามพยายามยัด inline แล้วโยน CapacityError ทีหลัง"""

def test_no_secret_appears_in_logs(caplog):
    """รัน embed+extract เต็มรอบ → ไม่มี byte ของคีย์ nonce หรือ ss
       ปรากฏใน log ที่ระดับ DEBUG"""
```

---

## 5. Data Contracts — ตารางอ้างอิงเร็ว

ชนิดข้อมูลที่ข้ามชั้น ถ้าจะแก้ตัวใดตัวหนึ่งต้องดูก่อนว่าใครใช้บ้าง

| Type | นิยามที่ | ประกอบด้วย | ผู้ผลิต | ผู้บริโภค |
|---|---|---|---|---|
| `Carrier` | `carrier/base.py` | ABC | `detect.open_carrier()` | `pipeline`, `analyzer`, `cost` |
| `Plane` | `domain/plane.py` | `values`, `changeable`, `meta` | `carrier.planes()` | `cost`, `coder`, `domain` |
| `(rho_p1, rho_m1)` | `cost/base.py` | `np.ndarray` คู่ · wet = `inf` | `CostModel.costs()` | `coder/stc` |
| `MessageKeys` | `crypto/ratchet/chain.py` | `aead`, `nonce`, `hdr`, `seed_sel`, `counter` | `SendChain`/`RecvChain` | `pipeline/engines` |
| `Header` | `crypto/header.py` | 12–16 B packed | `header.pack()` | `pipeline/extract` |
| `EmbedRequest` / `EmbedResult` | `pipeline/embed.py` | dataclass | `ui`, `research` | `pipeline` |
| `RunContext` | `pipeline/context.py` | `progress`, `logger`, `cancel_token` | `ui` | ทุกชั้นใน pipeline |
| `PipelineConfig` | `pipeline/yaml/schema.py` | `steps`, `variables`, `outputs` | `yaml/loader` | `pipeline`, `validate` |
| analysis report | `analyzer/dispatcher.py` | `dict` (ยังไม่มี schema) | `analyze()` | `ui`, `compare` |

> **หนี้ที่ควรใช้คืน:** report ของ analyzer เป็น `dict` ที่ไม่มี schema ทำให้ GUI ต้องเดา key และพังเงียบเมื่อโครงเปลี่ยน ควรทำเป็น dataclass ในเฟส 7

---

## 6. แผนที่ความสัมพันธ์ระหว่าง Component

### 6.1 ใครเรียกใคร

```
main.py
  └─ app/container.build_container()
       └─ ui/gui/main_window.MainWindow
            ├─ pages/embed_page ────────► pipeline/embed.run_embed()
            │                                ├─► carrier/detect.open_carrier()
            │                                ├─► pipeline/registry.resolve()
            │                                ├─► engines/juniward_stc
            │                                │     ├─► cost/juniward.costs()
            │                                │     ├─► crypto/ratchet.next_message_keys()
            │                                │     ├─► crypto/aead.seal()
            │                                │     ├─► crypto/header.whiten()
            │                                │     ├─► domain/selection.permute()
            │                                │     └─► coder/stc.embed()
            │                                └─► carrier.save()
            │
            ├─ pages/extract_page ──────► pipeline/extract.run_extract()
            ├─ pages/analyzer_page ─────► analyzer/dispatcher.analyze()
            │                                ├─► formats/{jpeg,png,wav,avi}_handler
            │                                ├─► modules/stat/*   (in-process)
            │                                ├─► modules/dct/*    (in-process)
            │                                └─► docker_bridge    (sandboxed)
            └─ pages/compare_page ──────► analyzer/compare.compare_results()
```

### 6.2 Coupling matrix — แก้ตรงนี้แล้วกระทบใคร

| ถ้าแก้... | กระทบ | ความเสี่ยง |
|---|---|---|
| `domain/plane.py` | **ทุกชั้นตั้งแต่ 5 ลงมา** | **สูงมาก** — ต้อง freeze หลังเฟส 1 |
| `carrier/base.py` | ทุก carrier + pipeline + analyzer | สูง |
| `crypto/header.py` หรือ `labels.py` | **ทำลาย backward compatibility ทั้งหมด** | **สูงมาก** — ต้องขึ้น `version` ใน header |
| `cost/base.py` | cost ทุกตัว + engines | กลาง |
| `coder/stc.py` | engines ที่ใช้ STC + ไฟล์เก่าทั้งหมดถอดไม่ได้ | **สูงมาก** |
| เพิ่ม carrier ใหม่ | ไม่กระทบใคร | ต่ำ ✔ |
| เพิ่ม cost model ใหม่ | ไม่กระทบใคร | ต่ำ ✔ |
| เพิ่ม engine ใหม่ | ไม่กระทบใคร (registry) | ต่ำ ✔ |
| แก้ GUI | ไม่กระทบใคร | ต่ำ ✔ |

สามแถวล่าง (ความเสี่ยงต่ำ) คือหลักฐานว่าการแบ่งชั้นทำงาน — งานที่ทำบ่อยที่สุดควรเป็นงานที่ปลอดภัยที่สุด

---

## 7. Configuration & File Formats

### 7.1 YAML pipeline

```yaml
version: 1
variables:
  cover:   "input/photo.jpg"
  payload: "input/secret.zip"

steps:
  - id: s1
    engine: juniward-stc
    inputs:
      cover:   "${var.cover}"
      payload: "${var.payload}"
      payload_rate: 0.1          # bpnzAC
      encryption: hybrid          # hybrid | password | none
    outputs:
      - "workspace/stego_01.jpg"

  - id: s2
    engine: metadata
    inputs:
      cover:   "${step.s1.out[0]}"   # รับ output ของขั้นก่อนหน้า
      payload: "input/note.txt"
    outputs:
      - "output/final.jpg"
```

| ส่วน | ตรวจโดย | กฎที่บังคับ |
|---|---|---|
| `version` | `yaml/schema.py` | ต้องตรงกับเวอร์ชันที่โปรแกรมรองรับ |
| `variables` | `yaml/validate.py` | path ต้องมีอยู่จริงตอนรัน |
| `steps[].engine` | `pipeline/registry.py` | ต้องลงทะเบียนแล้วและรองรับ domain ของ cover |
| `${step.X.out[n]}` | `yaml/validate.py` | ต้องไม่เป็นวงจร · index ต้องไม่เกินจำนวน output จริง |
| `payload_rate` | `domain/capacity.py` | ต้องไม่เกิน capacity ที่ carrier + h นั้นรองรับ |

### 7.2 Header bit layout

```
        MSB                                                          LSB
byte 0  │ version (4) │ suite (4)                                       │
byte 1-4│ session id (32)                                               │
byte 5-7│ counter (24)                                                  │
byte 8-10│ ciphertext length (24)                                       │
byte 11 │ flags (8)                                                     │
        │   bit0 = has_precover        bit1 = multipart                │
        │   bit2-3 = envelope mode     bit4 = auth mode                │
        │   bit5 = session bootstrap   bit6-7 = reserved (ต้องเป็น 0)  │
─────────── compact = 12 B จบตรงนี้ ───────────
byte 12-15│ carrier binding tag (32)  = truncate(fingerprint, 4 B)      │
─────────── bound = 16 B ───────────

ทั้งก้อนถูก XOR ด้วย keystream จาก HKDF(K_hdr_session) ก่อนนำไปฝัง
```

รายละเอียดระดับ bit ฉบับสมบูรณ์อยู่ใน `docs/FORMAT_SPEC.md` (ยังไม่เขียน)

### 7.3 ไฟล์ที่ระบบเขียนลงดิสก์

| ไฟล์ | ที่อยู่ | เนื้อหา | ความอ่อนไหว |
|---|---|---|---|
| stego output | ผู้ใช้เลือก | ไฟล์สื่อที่มีข้อมูลฝัง | **สูง** |
| `ratchet.state` | workspace | chain key + counter (เข้ารหัส AEAD) | **สูงมาก** — หลุด = ถอดข้อความอนาคตได้ |
| `*.key` | ผู้ใช้เลือก | private key (wrap ด้วย Argon2id) | **สูงมาก** |
| `analysis_report.json` | workspace | ผลวิเคราะห์ | ต่ำ |
| log | workspace | ต้องผ่าน `RedactingFilter` | กลาง |
| **`<sid>.sess`** (session envelope) | ผู้ใช้เลือก | eph pk + ML-KEM ct + auth material | **สูง** — ไม่ลับเท่าคีย์ แต่เปิดเผยว่ามี session อยู่ |
| **`identity.key`** | keystore | static KEM + signing key | **สูงมาก** |
| **`trust_store.db`** | workspace | identity ของคู่สนทนา + revocation | กลาง — เปิดเผยว่าคุยกับใคร |
| temp ของ analyzer | container `/tmp` | ลบเมื่อ container จบ | กลาง |

### 7.4 Session Envelope Format ★ P0

```
SessionEnvelope
┌──────────────────────────────────────────────────────────┐
│ magic "SI3S"          4 B    ← ไฟล์แยก จึงมี magic ได้     │
│ version               1 B                                │
│ suite                 1 B                                │
│ auth_mode             1 B    AUTH_IMPLICIT | AUTH_PQ_EXPLICIT │
│ envelope_mode         1 B                                │
│ sid                   4 B                                │
│ sender_fingerprint   32 B                                │
│ recipient_fingerprint 32 B                               │
│ eph_x25519_pk        32 B                                │
│ mlkem_ct           1088 B                                │
│ signature      0 หรือ 3373 B  (Ed25519 64 ‖ ML-DSA-65 3309) │
└──────────────────────────────────────────────────────────┘
รวม 1,196 B (implicit)  /  4,569 B (explicit)
```

**ข้อควรระวังที่ต่างจาก header:** envelope นี้อยู่เป็นไฟล์แยก **จึงมี magic string ได้** เพราะไม่ได้ถูกฝังในภาพ — ตรงข้ามกับ header ที่ห้ามมีโครงสร้างใดๆ เด็ดขาด
แต่การมีไฟล์ `.sess` วางอยู่ก็เป็นหลักฐานในตัวมันเองว่ามีการใช้ระบบนี้ ผู้ใช้ต้องรู้เรื่องนี้ และ `ENVELOPE_INLINE` มีไว้สำหรับกรณีที่ต้องการหลีกเลี่ยงจุดนี้ (แลกกับความจุตาม §2.7.2)

**เมื่อ `envelope_mode = INLINE`** โครงเดียวกันนี้ถูกฝังลงในภาพ **โดยตัด magic ออก** และผ่าน whitening เหมือน header

---

## 8. Extension Guide

### 8.1 เพิ่ม format ใหม่ (Phase 2 — เช่น BMP)

> Phase 1 จงใจรองรับแค่ jpg/png (ดู §4.2) หัวข้อนี้คือขั้นตอนสำหรับตอนที่เปิดสโคปแล้ว
> เหตุผลที่ยังเขียนไว้ตอนนี้: ถ้าขั้นตอนนี้ยาวกว่า 5 ข้อเมื่อไหร่ แปลว่าการแบ่งชั้นเริ่มรั่ว และควรแก้ก่อนที่จะเพิ่ม format จริง

1. สร้าง `carrier/image/bmp.py` สืบทอด `Carrier`
2. ประกาศ `suffixes`, `magic`, `domain`, `lossless_roundtrip`, `security_tier`
3. เขียน `load / planes / apply / save / fingerprint`
4. ลงทะเบียนใน `app/container.py` (1 บรรทัด)
5. เพิ่ม fixture ใน `tests/fixtures/` แล้วเขียน `test_bmp_roundtrip_is_byte_exact`

**ไม่ต้องแตะ:** pipeline, cost, coder, crypto, GUI — GUI จะเห็น format ใหม่เองจาก registry
**ถ้า tier ไม่ใช่ `strong`:** ต้องเพิ่มการเตือนใน UI ก่อน merge (ดู §4.8 ท้ายตาราง)

### 8.2 เพิ่ม cost model ใหม่ (เช่น MiPOD)

1. สร้าง `cost/mipod.py` สืบทอด `CostModel` ประกาศ `domains`
2. เขียน `costs()` คืน `(rho_p1, rho_m1)` · wet = `np.inf`
3. ลงทะเบียนใน `container.py`
4. เพิ่มลง `research/experiments/payload_sweep.yaml` เพื่อวัดผลเทียบกับตัวอื่น

### 8.3 เพิ่ม engine ใหม่

1. สร้าง `pipeline/engines/xxx.py` สืบทอด `Engine`
2. ประกาศ `engine_id`, `supported_domains`
3. เขียน `embed()` / `extract()` โดยประกอบชั้นล่างที่มีอยู่ ไม่เขียน math ใหม่ในนี้
4. ลงทะเบียนใน `container.py`
5. GUI จะขึ้น dropdown ให้อัตโนมัติผ่าน `registry.for_domain()`

### 8.4 เปลี่ยน crypto suite

**อย่าแก้ของเดิม — เพิ่ม suite ใหม่แล้วขึ้นเลข**

1. เพิ่มค่าใน `crypto/kdf/labels.py` เป็น `/v2`
2. เพิ่ม suite id ใหม่ในตารางของ `header.py`
3. เก็บ path ของ suite เก่าไว้อ่านไฟล์เดิมได้
4. เพิ่ม KAT ของ suite ใหม่ใน `tests/vectors/`

การแก้ label เดิมทับลงไปจะทำให้ไฟล์ที่ฝังไว้แล้วทั้งหมดถอดไม่ได้อีกเลย

---

## 9. Build, Run, Deploy

### 9.1 ตั้งเครื่อง dev

```bash
git clone <repo> && cd SIENG2_2
uv venv && uv pip install -e ".[gui,analyzer,dev]"
python -m sieng.coder._native.build      # build STC kernel
pytest tests/unit tests/vectors -q
docker compose -f docker/compose.yaml build analyzer
```

### 9.2 รัน

| งาน | คำสั่ง |
|---|---|
| GUI | `python main.py` |
| ฝัง (CLI) | `sieng embed cover.jpg -p secret.zip --engine juniward-stc --rate 0.1` |
| ถอด (CLI) | `sieng extract stego.jpg --key my.key -o out/` |
| วิเคราะห์ | `sieng analyze suspect.jpg --json report.json` |
| เทียบ | `sieng compare cover.jpg stego.jpg` |
| รัน pipeline | `sieng pipeline run templates/03_multicover_fanout.yaml` |

### 9.3 CI (GitHub Actions)

| Job | ทำอะไร | บล็อกการ merge ไหม |
|---|---|:---:|
| `lint` | ruff check + format | ใช่ |
| `types` | mypy --strict บน `crypto`, `coder`, `carrier`, `domain` | ใช่ |
| `imports` | import-linter ตรวจตารางในหัวข้อ 2.2 | ใช่ |
| **`sast`** | bandit + semgrep (ruleset crypto/injection) | ใช่ |
| **`secrets`** | gitleaks — กันคีย์จริงหลุดเข้า repo | **ใช่** |
| **`deps`** | pip-audit เทียบ CVE database | ใช่ (fail ที่ระดับ high ขึ้นไป) |
| **`sbom`** | cyclonedx-bom สร้าง SBOM แนบเป็น artifact | ไม่ (แต่ต้องมีทุก build) |
| **`container-scan`** | trivy สแกน image ของ analyzer | ใช่ |
| `unit` | pytest บน ubuntu + windows | ใช่ |
| `vectors` | KAT ทั้งหมด (ML-KEM, ML-DSA, HKDF, GCM-SIV, STC) | **ใช่ — ห้ามข้ามทุกกรณี** |
| `security` | negative test ทั้งหมดรวม MITM / rollback / concurrency | **ใช่** |
| **`fuzz-smoke`** | รัน fuzz แต่ละ target 60 วินาที | ใช่ |
| `integration` | pipeline 5 เทมเพลต | ใช่ |
| **`fuzz-long`** *(nightly)* | 1 ชม./target + อัปเดต corpus | ไม่ |
| `research-smoke` | รัน DCTR บน 50 ภาพ ดูว่าไม่ crash | ไม่ |

### 9.4 เรื่องที่ยังต้องตัดสินใจก่อน release

| ประเด็น | ทางเลือก | ผลกระทบ |
|---|---|---|
| License | MIT / Apache-2.0 / ไม่เผยแพร่ | ถ้าใช้ dataset หรือโค้ดอ้างอิงต้องเช็กเงื่อนไขก่อน |
| จะแจก binary ไหม | แจก / ให้ build เอง | เครื่องมือ steganography ที่แจก binary มักโดน antivirus flag |
| STC wheel | build ให้ / ให้ผู้ใช้ compile | กระทบความง่ายในการติดตั้งอย่างมาก |
| คำเตือนการใช้งาน | มี / ไม่มี | ควรมี — ระบุขอบเขตการใช้งานที่ตั้งใจไว้ให้ชัด |

### 9.5 Release Artifact ★ P2

**แยกให้ชัดระหว่างสองเรื่องที่มักถูกปนกัน**

| | Software build reproducibility | Research reproducibility |
|---|---|---|
| ถามว่า | build ซ้ำแล้วได้ binary เดิมไหม | รันทดลองซ้ำแล้วได้ตัวเลขเดิมไหม |
| ต้องมี | lockfile, pinned toolchain, `SOURCE_DATE_EPOCH` | seed, dataset hash, experiment config, commit |
| ระดับความยาก | สูง (Python + native ext ทำได้ยาก) | ปานกลาง |
| ความสำคัญกับโปรเจกต์นี้ | กลาง | **สูง — เป็น research framework** |

ทุก release ต้องแนบ `MANIFEST.json`

```json
{
  "version": "1.0.0",
  "commit": "a1b2c3d...",
  "build_time": "2026-08-11T00:00:00Z",
  "artifacts": [{"name": "sieng-1.0.0.whl", "sha256": "..."}],
  "sbom": "sbom.cyclonedx.json",
  "dependency_lock_sha256": "...",
  "crypto_suites": ["x25519-mlkem768-gcmsiv/v1"],
  "datasets": [{"name": "BOSSbase", "version": "1.01", "sha256": "..."}],
  "experiments": ["payload_sweep.yaml", "quality_sweep.yaml"],
  "known_gaps": ["C-level fuzzing of libjpeg binding", "OS-level monotonic counter"]
}
```

ช่อง `known_gaps` มีไว้โดยเจตนา — การประกาศสิ่งที่ยังไม่ได้ทำคือส่วนหนึ่งของความน่าเชื่อถือ ไม่ใช่จุดอ่อนที่ต้องซ่อน

---

## 10. Migration Mapping — ไฟล์เก่า → ไฟล์ใหม่

| ไฟล์ปัจจุบัน | ไปที่ | ประเภทงาน |
|---|---|---|
| `main.py` | `main.py` (เหลือ ~5 บรรทัด) + `app/container.py` + `ui/gui/bootstrap.py` | แยก |
| `src/core/stego/lsb_pp.py` | **แตกเป็น 4 ไฟล์** → `carrier/image/png.py` (chunk I/O) · `cost/legacy_texture.py` (gradient+entropy) · `coder/opap.py` (OPAP) · `pipeline/engines/lsbpp.py` (ประสาน) | **ผ่าตัดใหญ่** |
| `src/core/stego/locomotive.py` | `pipeline/engines/locomotive.py` + ส่วน append ย้ายเข้า carrier · **จำกัดเหลือ jpg/png** | แยก + ลดสโคป |
| `src/core/stego/metadata.py` | `pipeline/engines/metadata.py` | ย้าย + ปรับ interface |
| `src/core/stego/metadata_handlers/png_handler.py` | `carrier/image/png.py` (ส่วน iTXt/custom chunk) | รวม |
| `src/core/stego/metadata_handlers/mp3_handler.py` | **ไม่ย้ายใน Phase 1** — เก็บไว้ใน git history รอ Phase 2 | เลื่อนออก |
| `src/core/crypto/sym_encrypt.py` | `crypto/kdf/argon2.py` + `crypto/aead/` (เลิกใช้ GCM ธรรมดา) | แยก + เลิกใช้บางส่วน |
| `src/core/crypto/asym_encrypt.py` | `crypto/kem/` — **RSA-3072 เข้าสถานะ deprecated** เก็บไว้อ่านไฟล์เก่าเท่านั้น | เลิกใช้ |
| `src/core/configurable/config_mode.py` | **แตกเป็น 5 ไฟล์** → `pipeline/yaml/{schema,loader,validate}.py` · `pipeline/{embed,extract}.py` · `pipeline/registry.py` | **ผ่าตัดใหญ่** |
| `src/core/analyzer/handle.py` | `analyzer/dispatcher.py` | เปลี่ยนชื่อ |
| `src/core/analyzer/cli.py` | `ui/cli/analyze.py` | ย้าย |
| `src/core/analyzer/compare_logic.py` | `analyzer/compare.py` | เปลี่ยนชื่อ |
| `src/core/analyzer/docker_bridge.py` | `analyzer/docker_bridge.py` | ย้าย |
| `src/core/analyzer/formats/*.py` | `analyzer/formats/*.py` | ย้าย |
| `src/core/analyzer/modules/**` | `analyzer/modules/**` | ย้าย |
| `src/core/analyzer/external_tools/*.py` | `analyzer/external_tools/*.py` | ย้าย |
| `src/core/analyzer/utils/text_extractor.py` | `analyzer/utils/text_extractor.py` | ย้าย |
| `src/gui/**` | `ui/gui/**` | ย้าย + แก้ import |
| `src/cli/{analyzer_cmd,stego_cmd}.py` | `ui/cli/{analyze,embed,extract}.py` | ย้าย + เปลี่ยนเป็น typer |
| `src/templates/*.yaml` | `pipeline/yaml/templates/*.yaml` | ย้าย |
| `tests/lsbpp_surface_analysis.py` | `research/notebooks/lsbpp_surface.ipynb` | ย้าย (ไม่ใช่ test จริง) |
| `requirements.txt` | `pyproject.toml` + lockfile | เขียนใหม่ (แก้ปัญหา UTF-16) |
| `docker/Dockerfile` | `docker/Dockerfile.analyzer` | เปลี่ยนชื่อ + เพิ่ม `.research` |

**ลำดับที่ปลอดภัยที่สุด:** ย้ายไฟล์ที่เป็นงาน "ย้าย" ล้วนก่อนทั้งหมด (analyzer + gui) ให้ระบบยังรันได้ปกติ แล้วค่อยผ่าตัด `lsb_pp.py` กับ `config_mode.py` ทีละไฟล์โดยมี integration test ครอบไว้ก่อน

---

## 11. Security Evaluation Matrix

### 11.1 สองแกนที่ต้องแยกจากกัน

ความปลอดภัยของระบบนี้ไม่ใช่ตัวเลขเดียว — มันมีสองแกนที่ไม่เกี่ยวข้องกันเลย และการเก่งแกนหนึ่งไม่ช่วยอีกแกน

```
SIENG3 Security
│
├── Cryptographic security  ── "ถ้าเขารู้ว่ามีข้อมูล เขาอ่านได้ไหม"
│   ├── Confidentiality        AES-256-GCM-SIV + hybrid KEM
│   ├── Integrity              AEAD tag
│   ├── Authentication         AUTH_IMPLICIT / AUTH_PQ_EXPLICIT
│   ├── Replay protection      counter + consumed set
│   ├── Forward secrecy        symmetric ratchet
│   └── Key compromise         ขอบเขตตาม §2.6.2
│
└── Steganographic security ── "เขารู้ไหมว่ามีข้อมูล"
    ├── Detectability          J-UNIWARD + STC → วัดด้วย P_E
    ├── Payload capacity       bpnzAC
    ├── Visual quality         PSNR / SSIM
    ├── Robustness             ★ ไม่รับประกัน (เป็น non-goal)
    └── Cover-source mismatch  ความสมเหตุสมผลของตัวเลขที่รายงาน
```

> **ระบบที่เข้ารหัสแน่นหนาที่สุดในโลกก็ยังล้มเหลวได้สมบูรณ์** ถ้าผู้ตรวจดูภาพแล้วรู้ทันทีว่ามีอะไรซ่อนอยู่ — เพราะเป้าหมายของ steganography คือไม่ให้มีคำถามตั้งแต่แรก การรีวิวที่ดูแต่แกนซ้ายจึงตอบได้แค่ครึ่งเดียว

### 11.2 ตาราง Threat × Mitigation × Test

ตารางนี้คือสัญญาว่าทุกภัยที่ระบุไว้มีทั้งการป้องกันและการทดสอบ ช่อง Status เติมเมื่อ implement เสร็จ

| # | Threat | Attack | Mitigation | Test | Status |
|:--:|---|---|---|---|:---:|
| T1 | MITM | สลับ public key ตอนตั้ง session | `AUTH_IMPLICIT` + transcript binding + fingerprint verification | `test_mitm_key_substitution_is_rejected` | ☐ |
| T2 | Transcript ambiguity | จัดเรียงฟิลด์ใหม่ให้ได้ transcript เดิม | length-prefix ทุกฟิลด์ | `test_transcript_canonicalization` | ☐ |
| T3 | Replay | ส่งไฟล์เดิมซ้ำ | counter + consumed set | `test_replay_rejected` | ☐ |
| T4 | Tamper | แก้ ciphertext หรือ carrier | AEAD tag + AAD | `test_tampered_ciphertext_rejected` | ☐ |
| T5 | Cross-carrier splice | ตัด payload ไปแปะภาพอื่น | AAD ผูก `carrier.fingerprint()` | `test_ciphertext_from_other_carrier_is_rejected` | ☐ |
| T6 | State rollback | คืนค่า state เก่า | monotonic generation + GCM-SIV เป็นตาข่าย | `test_state_rollback_is_detected` | ☐ |
| T7 | Concurrent writer | สอง process ใช้ counter เดียวกัน | exclusive lock ครอบ read-modify-write | `test_two_processes_cannot_use_same_counter` | ☐ |
| T8 | Crash mid-commit | ไฟดับระหว่างเขียน state | atomic commit + เซฟก่อนเขียน stego | `test_crash_during_commit_never_reuses_counter` | ☐ |
| T9 | Ratchet DoS | ส่ง counter = 2²⁴−1 | `max_ratchet_skip` | `test_ratchet_limit_enforced` | ☐ |
| T10 | Parser RCE | ไฟล์ที่ออกแบบมาโจมตี libjpeg/binwalk | container ตาม §4.8 + input limits | `test_malformed_input_contained` | ☐ |
| T11 | Resource exhaustion | decompression bomb, fork bomb | memory/CPU/PID limit + timeout | `fuzz_jpeg` + `test_bomb_rejected` | ☐ |
| T12 | Header leak | header มี pattern ให้จับ | whitening ด้วย `K_hdr_session` | `test_header_bits_are_indistinguishable_from_random` | ☐ |
| T13 | Double compression | บันทึก JPEG ซ้ำ | เข้า-ออกที่ระดับ coefficient | `test_jpeg_roundtrip_is_byte_exact` | ☐ |
| T14 | Metadata leak | EXIF บอกกล้อง เวลา พิกัด | metadata policy + คำเตือนใน UI | `test_metadata_policy_applied` | ☐ |
| T15 | Secret in logs | คีย์โผล่ใน log/traceback | `RedactingFilter` | `test_no_secret_appears_in_logs` | ☐ |
| T16 | Revoked identity | ใช้ identity ที่ถูกเพิกถอน | `TrustStore.is_revoked()` | `test_revoked_identity_is_refused` | ☐ |
| T17 | Capacity overreach | ยัด envelope ลงภาพที่เล็กเกินไป | `choose_mode()` ตัดสินจากความจุจริง | `test_envelope_mode_respects_capacity` | ☐ |
| T18 | Steganalysis | DCTR / GFR / SRNet | J-UNIWARD + STC + selection channel ต่อไฟล์ | `research/experiments/*` | ☐ |
| T19 | Cover-source mismatch | detector เรียนรู้ artifact ของ dataset | ทดสอบ cross-source แล้วรายงานผล | `cover_source_mismatch.yaml` | ☐ |
| T20 | Supply chain | dependency ถูกแทรกโค้ดร้าย | pin + hash + SBOM + audit + trivy | CI jobs `deps`, `sbom`, `container-scan` | ☐ |

### 11.3 ภัยที่รู้ว่ายังป้องกันไม่ได้ (known gaps)

ประกาศไว้ให้ชัดดีกว่าปล่อยให้เข้าใจผิด

| Gap | เหตุผล | แผน |
|---|---|---|
| Post-compromise security | ไม่มี re-KEM ใน Phase 1 | Phase 2 |
| Rollback โดยผู้โจมตีที่ตั้งใจ | state ในไฟล์ย้อนได้เสมอ | Phase 2 (TPM / OS counter) |
| Memory compromise | Python zeroize ไม่สมบูรณ์ | ประกาศเป็นนอกขอบเขต |
| C-level memory bug ใน libjpeg | fuzzing ฝั่ง Python เข้าไม่ถึง | ชดเชยด้วย sandbox · Phase 2 ใช้ libFuzzer |
| PQ sender authentication แบบไม่มี signature | ข้อจำกัดของ ML-KEM เอง | `AUTH_PQ_EXPLICIT` เมื่อความจุอำนวย |
| Robustness ต่อการบีบอัดซ้ำ | ขัดกับเป้าหมาย undetectability | non-goal ถาวร |
| Deniability | header ที่ถอดได้คือหลักฐาน | non-goal |

---

## 12. Priority Roadmap

### 12.1 P0 — ต้องเสร็จ **ก่อนเขียนโค้ด crypto บรรทัดแรก**

| # | งาน | ส่งมอบอะไร | ทำไมต้องก่อน |
|:--:|---|---|---|
| P0-1 | **Threat model** | `docs/THREAT_MODEL.md` | ถ้าไม่รู้ว่ากันใคร ก็ตัดสินใจอะไรไม่ได้เลย |
| P0-2 | **Session protocol + authentication** | `docs/SESSION_PROTOCOL.md` + `crypto/auth/` | MITM ทำให้ทุกอย่างที่เหลือไร้ความหมาย |
| P0-3 | **Session envelope** | `docs/FORMAT_SPEC.md` + `crypto/envelope.py` | ตัดสินใจผิดตอนนี้ = รื้อ format ทีหลัง |
| P0-4 | **Anti-rollback / concurrency** | `state_lock` + `generation` + `rollback_guard` | ออกแบบทีหลังแปลว่าต้องเปลี่ยนรูปแบบ state file |

**ลำดับที่ถูกต้อง:** `THREAT_MODEL` → `SESSION_PROTOCOL` → `FORMAT_SPEC` → implementation → KAT → fuzzing → security test → research evaluation → release
เอกสารสามฉบับแรกเป็นเอกสารล้วน ไม่มีโค้ด — และนั่นคือประเด็น เพราะการเปลี่ยนใจในเอกสารมีต้นทุนเป็นชั่วโมง แต่ในโค้ดที่ปล่อยไปแล้วมีต้นทุนเป็นการทำลาย backward compatibility ทั้งหมด

### 12.2 P1 — ต้องเสร็จก่อน release

| # | งาน | อยู่ที่หัวข้อ |
|:--:|---|---|
| P1-1 | Parser resource limits + sandbox hardening | §4.8 |
| P1-2 | Fuzzing harness 6 target | §4.12 |
| P1-3 | Key lifecycle + rotation + revocation | §4.6 `lifecycle/` |
| P1-4 | Security evaluation matrix เติมครบทุกช่อง | §11.2 |
| P1-5 | Cross-quality evaluation (QF 50–95) | §4.11 |
| P1-6 | Cross-dataset evaluation (BOSS ↔ ALASKA) | §4.11 |
| P1-7 | Cover-source mismatch | §4.11 |
| P1-8 | Confidence interval + N + seed ในทุกผล | §4.11 |
| P1-9 | SBOM + dependency scan + SAST + secret scan | §9.3 |

### 12.3 P2 — Phase 2

| # | งาน | หมายเหตุ |
|:--:|---|---|
| P2-1 | Re-KEM / post-compromise recovery | เปลี่ยนโครง session — ต้องขึ้น suite version |
| P2-2 | OS-level monotonic counter (TPM / Keychain / DPAPI) | ผูกกับแพลตฟอร์ม กระทบการย้ายเครื่อง |
| P2-3 | Reproducible build | ยากกับ Python + native ext |
| P2-4 | C-level fuzzing ของ libjpeg binding | ต้องใช้ libFuzzer/AFL++ |
| P2-5 | Advanced key rotation policy | อัตโนมัติตามรอบเวลา |
| P2-6 | เพิ่ม carrier กลับเข้ามา — `bmp` `tiff` `webp` (spatial, tier strong) | **ทำก่อนกลุ่มอื่น** เพราะใช้ `HillCost` เดิมได้เลย แทบไม่มีโค้ดใหม่ |
| P2-7 | เพิ่ม carrier tier อ่อน — `wav` `mp3` `avi` `mp4` `blob` | **ไม่เร่ง** — ต้องมี UI เตือน tier ก่อน ไม่งั้นผู้ใช้เข้าใจผิด |
| P2-8 | carrier ใหม่ทั้งหมด — `heic` `av1` | ไม่เร่ง |

### 12.4 สิ่งที่ **ห้าม** เพิ่มในเฟสนี้

`H.264 / video codec embedding` · `network messaging` · `anti-forensics` · `cloud service` · `database` · `AI-generated adaptive steganography`

ทั้งหมดนี้ขยาย attack surface โดยไม่ตอบคำถามวิจัยหลัก — และสองอันแรก (network transport, anti-forensics) เป็น **non-goal ถาวร** ตาม §1.5 ไม่ใช่แค่เลื่อนออกไป

### 12.5 สรุปสถานะการรีวิว

| | |
|---|---|
| **สถาปัตยกรรม** | แข็งแรง — การแบ่งชั้นถูกต้อง ทำให้เพิ่ม format/algorithm ได้โดยไม่กระทบส่วนอื่น |
| **สิ่งที่ยังขาด** | ไม่ใช่ปัญหาของสถาปัตยกรรม แต่เป็น **รายละเอียดของ protocol ที่ยังไม่ถูกกำหนด** |
| **คำตัดสิน** | **ผ่านแบบมีเงื่อนไข** — เริ่ม implementation ได้เมื่อ P0 ทั้งสี่ข้อเสร็จ |
| **คำแนะนำหลัก** | **หยุดเพิ่มฟีเจอร์ ทำ protocol ให้ชัดก่อน** ทุกฟีเจอร์ที่เพิ่มตอนนี้จะต้องถูกรื้อเมื่อ format spec เปลี่ยน |

---

## 13. Glossary

| คำ | ความหมาย |
|---|---|
| **cover** | ไฟล์ต้นฉบับก่อนฝังข้อมูล |
| **stego** | ไฟล์หลังฝังข้อมูลแล้ว |
| **precover** | ภาพก่อนถูกบีบอัดเป็น JPEG — ถ้ามี จะใช้ SI-UNIWARD ได้ซึ่งปลอดภัยกว่า |
| **payload** | ข้อมูลลับที่ต้องการซ่อน |
| **bpnzAC** | bits per non-zero AC coefficient — หน่วยวัดปริมาณข้อมูลที่ฝังใน JPEG |
| **quantized DCT** | สัมประสิทธิ์ DCT หลังหารด้วย quantization table — เป็นสิ่งที่ JPEG เก็บจริงในไฟล์ |
| **wet paper / wet pixel** | ตำแหน่งที่แก้ไม่ได้ (เช่น AC ที่เป็นศูนย์) กำหนด cost เป็นอนันต์ |
| **STC** | Syndrome-Trellis Codes — เข้ารหัสเชิงกลุ่มที่หาชุดการแก้ค่าที่ distortion รวมต่ำสุด |
| **h (constraint height)** | พารามิเตอร์ของ STC แลกความเร็วกับประสิทธิภาพ ปกติ 10–12 |
| **J-UNIWARD** | distortion model มาตรฐานสำหรับ JPEG |
| **SI-UNIWARD** | รุ่น side-informed ของ UNIWARD ใช้เมื่อมี precover |
| **UERD / HILL** | distortion model ทางเลือก — UERD สำหรับ DCT (เร็วกว่า), HILL สำหรับ spatial |
| **selection channel** | ลำดับลับของการเลือก coefficient ที่จะฝัง มาจาก `seed_sel` |
| **DCTR / GFR** | feature extractor สำหรับ steganalysis ของ JPEG (8k และ 17k มิติ) |
| **SRNet** | deep learning detector ที่เป็นมาตรฐานปัจจุบัน |
| **P_E** | minimal total probability of error under equal priors — ตัวเลขหลักที่ใช้รายงานผล ยิ่งใกล้ 0.5 ยิ่งดี (detector เดาสุ่ม) |
| **KEM** | Key Encapsulation Mechanism — กลไกแลกความลับด้วยกุญแจสาธารณะ |
| **ML-KEM-768** | มาตรฐาน post-quantum KEM (FIPS 203) เดิมชื่อ Kyber |
| **AEAD** | Authenticated Encryption with Associated Data — เข้ารหัสพร้อมพิสูจน์ความถูกต้อง |
| **AAD** | ข้อมูลที่ถูกพิสูจน์แต่ไม่ถูกเข้ารหัส — ในระบบนี้คือ header + carrier fingerprint |
| **GCM-SIV** | โหมด AEAD ที่ทนต่อการใช้ nonce ซ้ำ (nonce misuse resistant) |
| **ratchet** | โซ่คีย์ที่เดินหน้าได้อย่างเดียว ย้อนกลับไม่ได้ |
| **forward secrecy** | คีย์ปัจจุบันหลุดแล้วข้อมูลในอดีตยังปลอดภัย |
| **KAT** | Known Answer Test — ทดสอบว่าผลลัพธ์ตรงกับ reference vector ทุก bit |
| **OPAP** | Optimal Pixel Adjustment Process — เทคนิคลดความผิดเพี้ยนของ LSB (ของเดิม) |
| **fail closed** | เมื่อเกิดข้อผิดพลาด ให้หยุดทำงาน ไม่ใช่ทำต่อด้วยวิธีที่ปลอดภัยน้อยกว่า |
| **MITM** | Man-in-the-Middle — ผู้โจมตีที่แทรกกลางแล้วสร้าง session แยกกับทั้งสองฝั่ง |
| **transcript binding** | ผูกทุกฟิลด์ของ handshake เข้ากับการคำนวณ session key เพื่อกันการสลับค่าระหว่างทาง |
| **canonicalization attack** | การจัดเรียงข้อมูลใหม่ให้ได้ค่า hash เดิม — ป้องกันด้วย length-prefix ทุกฟิลด์ |
| **AUTH_IMPLICIT** | พิสูจน์ตัวตนโดยใส่ DH ของ static key เข้าไปใน key derivation (แนวคิด auth mode ของ HPKE) — overhead 0 byte |
| **AUTH_PQ_EXPLICIT** | พิสูจน์ตัวตนด้วยลายเซ็น Ed25519 + ML-DSA-65 — overhead 3,373 B |
| **ML-DSA-65** | มาตรฐาน post-quantum signature (FIPS 204) เดิมชื่อ Dilithium |
| **prekey bundle** | ชุด public key ถาวรของผู้ใช้ที่แจกล่วงหน้าผ่านช่องทางที่เชื่อได้ ทำให้ไม่ต้องส่งซ้ำทุกข้อความ |
| **fingerprint verification** | การที่ผู้ใช้สองคนเทียบ hash ของ identity กันเองนอกระบบ — จุดที่ trust เริ่มต้นจริง |
| **session envelope** | ข้อมูลที่ผู้รับต้องมีเพื่อสร้าง session ได้ (eph pk + KEM ciphertext + auth material) |
| **PCS** | Post-Compromise Security — กู้ความปลอดภัยกลับมาได้หลังคีย์หลุด **ไม่มีใน Phase 1** |
| **re-KEM** | รันการแลกคีย์ใหม่เป็นระยะเพื่อรีเซ็ต chain — กลไกที่ทำให้เกิด PCS |
| **monotonic generation** | ตัวนับที่เพิ่มอย่างเดียว ใช้ตรวจจับว่า state ถูกย้อนกลับ |
| **rollback attack** | คืนค่า state เก่าเพื่อบังคับให้ระบบใช้ counter/คีย์ซ้ำ |
| **nonce misuse resistance** | คุณสมบัติของ GCM-SIV ที่ทำให้ nonce ซ้ำไม่ทำให้คีย์รั่ว |
| **decompression bomb** | ไฟล์เล็กที่ขยายเป็นข้อมูลมหาศาลตอนคลาย ใช้ทำ DoS ต่อ parser |
| **fuzzing** | ป้อน input ที่ผิดรูปจำนวนมากอัตโนมัติเพื่อหา crash / hang / พฤติกรรมผิดปกติ |
| **SAST** | Static Application Security Testing — สแกนหาช่องโหว่จากซอร์สโค้ดโดยไม่รัน |
| **SBOM** | Software Bill of Materials — รายการ dependency ทั้งหมดพร้อมเวอร์ชันและ hash |
| **cover-source mismatch (CSM)** | สถานการณ์ที่ detector ถูกเทรนกับภาพจากแหล่งหนึ่งแต่ทดสอบกับอีกแหล่ง — วัดว่า detector เรียนรู้ร่องรอยการฝังจริงหรือแค่จำ dataset |
| **QF (quality factor)** | ระดับคุณภาพของ JPEG (50–95) มีผลต่อจำนวน non-zero AC และความยากในการตรวจจับ |
| **confidence interval** | ช่วงความเชื่อมั่นของค่าที่วัดได้ — ต้องรายงานคู่กับ P_E เสมอ |
| **robustness** | ความทนทานของ payload ต่อการบีบอัดซ้ำ/resize — **เป็น non-goal ของโปรเจกต์นี้** |
| **deniability** | ความสามารถปฏิเสธได้ว่าไม่ได้ส่งข้อความ — ระบบนี้ไม่มี |
| **non-repudiation** | ผู้ส่งปฏิเสธไม่ได้ว่าเป็นคนส่ง — ได้จาก `AUTH_PQ_EXPLICIT` เท่านั้น |

---

*เอกสารนี้ควรอัปเดตทุกครั้งที่โครงสร้างเปลี่ยน · เมื่อโครงจริงเสร็จแล้ว ควรมี CI job ตรวจว่าโครงสร้างโฟลเดอร์จริงตรงกับหัวข้อ 3*
