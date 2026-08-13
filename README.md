# SIENG3

Steganography Integrated ENGine, generation 3 — เครื่องมือฝังข้อมูลลับในภาพแบบ adaptive
พร้อมการเข้ารหัสไฮบริดที่ทนต่อคอมพิวเตอร์ควอนตัม และกรอบการวัดผลเชิงวิชาการที่ทำซ้ำได้

> **สถานะ: อยู่ระหว่างพัฒนา ยังใช้งานไม่ได้**
> โครงสร้างพร้อมแล้ว แต่โค้ดทำงานยังไม่ถูกเขียน — ดู `docs/PROJECT_CONTEXT.md` §1 สำหรับสถานะจริง

---

## ทำอะไรได้

| ความสามารถ | วิธีการ |
|---|---|
| **ฝัง** ข้อมูลใน JPEG | J-UNIWARD + STC บน quantized DCT coefficient โดยไม่บีบอัดซ้ำ |
| **ฝัง** ข้อมูลใน PNG | HILL + STC บน spatial domain |
| **เข้ารหัส** | X25519 + ML-KEM-768 → HKDF-SHA256 → AES-256-GCM-SIV พร้อม symmetric ratchet |
| **ถอด** ข้อมูลกลับ | ตรวจสอบความถูกต้องด้วย AEAD ที่ผูกกับพาหะ |
| **วิเคราะห์** ไฟล์ต้องสงสัย | โครงสร้าง · metadata · สถิติ (chi-square, RS, WS, SPA) · DCT |
| **วัดผล** | DCTR + GFR + SRNet บน BOSSbase และ ALASKA2 |

**Phase 1 รองรับ carrier แค่ `.jpg` และ `.png`** — ไฟล์ชนิดอื่นจะถูกปฏิเสธอย่างชัดเจน ไม่มีการ fallback
(`analyzer` วิเคราะห์ได้กว้างกว่านั้น เพราะเป็นคนละหน้าที่ — ดู `docs/PROJECT_CONTEXT.md` §2.4)

---

## ติดตั้ง

ต้องมี **Python 3.11 ขึ้นไป**

```
pip install -e ".[gui,analyzer,dev]"
```

ทางเลือกอื่น (ลงทุกอย่างรวม `torch` ที่หนักหลาย GB)

```
pip install -r requirements.txt
```

เครื่องมือภายนอกบางตัว (`exiftool`, `binwalk`, `zsteg`, `pngcheck`, `mediainfo`) ลงผ่าน pip ไม่ได้
ระบบเรียกใช้ผ่าน Docker container ที่จำกัดทรัพยากรและตัด network — ดู `docker/`

---

## ใช้งาน

```
python main.py                       # GUI
sieng embed cover.jpg -p secret.zip  # CLI
sieng extract stego.jpg --key my.key
sieng analyze suspect.jpg
```

---

## พัฒนา

การตรวจสอบทั้งหมดรันในเครื่อง ไม่พึ่งบริการภายนอก

```
nox                  # รันทุก session
nox -s lint types    # ตรวจเร็ว
nox -s vectors       # KAT — ห้ามข้าม
nox -s security      # negative test — ห้ามข้าม
scripts/check.sh     # ชุดมาตรฐาน (Windows ใช้ scripts/check.ps1)
```

---

## เอกสาร

| ไฟล์ | อ่านเมื่อไหร่ |
|---|---|
| `docs/PROJECT_CONTEXT.md` | **อ่านก่อนเริ่มงานทุกครั้ง** — สถานะปัจจุบัน ข้อตกลง scope งานรายโมดูล |
| `docs/PROJECT_STRUCTURE.md` | อ้างอิงสถาปัตยกรรม สัญญาของแต่ละชั้น เหตุผลการออกแบบ |
| `SECURITY.md` | ขอบเขตด้านความปลอดภัยและวิธีรายงานปัญหา |

---

## ข้อจำกัดที่ประกาศไว้ตั้งแต่ต้น

ระบบนี้ **ไม่** รับประกันสิ่งเหล่านี้ และไม่ได้ตั้งใจจะทำ

- **Robustness** — ถ้าไฟล์ถูกบีบอัดซ้ำ ย่อ หรือครอบตัด ข้อมูลที่ฝังหายทั้งหมด
- **Post-compromise security** — Phase 1 มีแค่ forward secrecy
- **Deniability** — ไฟล์ที่มี header ถูกต้องคือหลักฐานเมื่อผู้ตรวจได้คีย์ไป
- **"ตรวจจับไม่ได้"** — ไม่มีระบบไหนรับประกันได้ เรารายงานเป็นค่า P_E ต่อ detector ที่ระบุชื่อเท่านั้น

รายละเอียดอยู่ใน `docs/PROJECT_STRUCTURE.md` §1.5 และ §2.6
