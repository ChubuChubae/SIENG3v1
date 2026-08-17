# SIENG3 — Session Protocol

> วิธีที่สองฝ่ายตกลงความลับร่วมกันและพิสูจน์ว่ากำลังคุยกับคนที่ตั้งใจจะคุยด้วย
> เอกสารนี้กำหนด **สิ่งที่ต้อง implement ให้ตรงทุก byte** — เดาไม่ได้ ตีความเองไม่ได้
> เวอร์ชัน 1.0 · Phase 1.2 · ขึ้นกับ `THREAT_MODEL.md` · layout ระดับ bit อยู่ใน `FORMAT_SPEC.md`

---

## 1. ปัญหาที่ protocol นี้แก้

`X25519 + ML-KEM-768` ตอบได้แค่ **"ฉันมีความลับร่วมกับใครบางคน"**
ไม่ได้ตอบว่า **"คนนั้นคือ Bob จริงไหม"**

ถ้าไม่มี authentication ผู้โจมตี (T3) สร้าง session แยกกับทั้งสองฝั่งแล้วอ่านทุกอย่างตรงกลางได้
และเพราะช่องทางส่งของระบบนี้เป็นช่องทางสาธารณะโดยธรรมชาติ ความเสี่ยงนี้สูงกว่าระบบแชตทั่วไปด้วยซ้ำ

**สิ่งที่ทำให้การออกแบบนี้ยากกว่าปกติ:** ความจุของพาหะน้อยมาก
ทุก byte ที่ใส่ลงไปในภาพแย่งที่กับ payload จริง protocol จึงต้องออกแบบให้ overhead ต่อภาพเป็นศูนย์ให้ได้

---

## 2. องค์ประกอบและขนาด

ตัวเลขจริงที่บังคับการออกแบบทั้งหมด

| องค์ประกอบ | ขนาด |
|---|---:|
| X25519 public key | 32 B |
| X25519 ciphertext (ephemeral pk ที่ส่งไป) | 32 B |
| ML-KEM-768 public key | 1,184 B |
| ML-KEM-768 ciphertext | 1,088 B |
| ML-KEM-768 shared secret | 32 B |
| Ed25519 public key / signature | 32 B / 64 B |
| ML-DSA-65 public key / signature | 1,952 B / 3,309 B |

เทียบกับความจุจริงของภาพมาตรฐานงานวิจัย (512×512 grayscale, QF75, non-zero AC ≈ 26,000)

| Payload rate | ความจุ |
|---|---:|
| 0.05 bpnzAC | ≈ 163 B |
| 0.10 bpnzAC | ≈ 325 B |
| 0.20 bpnzAC | ≈ 650 B |
| 0.40 bpnzAC | ≈ 1,300 B |

**ML-KEM ciphertext ก้อนเดียว (1,088 B) เกินความจุที่ 0.1 bpnzAC ไป 3.3 เท่า**
ถ้าเพิ่มลายเซ็น PQ เข้าไปด้วยจะกลายเป็น ≈ 4.5 KB ซึ่งเกินความจุที่ 0.4 bpnzAC ไป 3.5 เท่า

ข้อสรุป: **session material ต้องไม่ถูกส่งซ้ำทุกภาพ** และ **authentication ต้องไม่กินความจุ**

---

## 3. Identity

### 3.1 โครงสร้าง

ผู้ใช้หนึ่งคนมี identity หนึ่งชุด สร้างครั้งเดียว ใช้ตลอด

```
Identity (public, แจกได้)          IdentitySecret (ลับ, เก็บใน keystore)
├── x25519_static_pk      32 B     ├── x25519_static_sk      32 B
├── mlkem_static_pk    1,184 B     ├── mlkem_static_sk    2,400 B
├── ed25519_pk            32 B     ├── ed25519_sk            32 B
└── mldsa_pk           1,952 B     └── mldsa_sk           4,032 B
```

`IdentitySecret` ต้อง wrap ด้วย Argon2id + AEAD เสมอเมื่อเก็บลงดิสก์ ไม่มีทางเก็บแบบดิบ

### 3.2 Fingerprint

```
fingerprint = SHA-256(
      LP(x25519_static_pk) || LP(mlkem_static_pk)
   || LP(ed25519_pk)       || LP(mldsa_pk)
)
```

แสดงต่อผู้ใช้เป็น 32 hex ตัวแรกจัดเป็น 8 กลุ่มกลุ่มละ 4 ตัว อ่านออกเสียงได้

```
3F2A 8B01 C4D9 77E2 5A16 90BC EE33 4108
```

`LP(x)` คือ length-prefix ดู §5.1

### 3.3 การเชื่อ identity ครั้งแรก — จุดที่ไม่มีเทคโนโลยีไหนช่วยได้

**การเชื่อครั้งแรกต้องเกิดนอกระบบเสมอ** ผู้ใช้สองคนต้องเทียบ fingerprint ผ่านช่องทางที่เชื่อได้จริง

| วิธี | บันทึกเป็น | ระดับความเชื่อถือ |
|---|---|---|
| เจอตัวกันแล้วสแกน QR | `verified_via="qr"` | สูงสุด |
| โทรหากันแล้วอ่าน fingerprint ให้ฟัง | `verified_via="voice"` | สูง (ถ้าจำเสียงกันได้) |
| พิมพ์ fingerprint เทียบเองจากช่องทางอื่น | `verified_via="manual"` | กลาง |
| กดยอมรับโดยไม่เทียบ | **ห้ามมีตัวเลือกนี้** | — |

**ข้อบังคับสำหรับ GUI (Phase 9.4)**

1. หน้าเพิ่ม identity ต้องแสดง fingerprint ขนาดใหญ่ อ่านง่าย
2. ผู้ใช้ต้อง **พิมพ์กลุ่มตัวอักษรอย่างน้อย 2 กลุ่มที่ระบบสุ่มถาม** จึงจะกดยืนยันได้
3. ปุ่มยืนยันต้องไม่ทำงานจนกว่าจะพิมพ์ถูก และ **ห้ามมีปุ่มข้าม**
4. ต้องบันทึกว่าเชื่อเพราะอะไร (`verified_via`) และแสดงให้เห็นทุกครั้งที่ใช้ identity นั้น

เหตุผล: ถ้าขั้นตอนนี้เป็น dialog ที่กด "ตกลง" ผ่านได้ ผู้ใช้จะกดผ่านทุกครั้ง แล้ว authentication ทั้งหมดที่สร้างมาไม่มีความหมาย — นี่คือสมมติฐาน A-1 ใน `THREAT_MODEL.md` §5

### 3.4 Revocation

`TrustStore` เก็บรายการ identity ที่ถูกเพิกถอน ตรวจทุกครั้งก่อนสร้าง session ใหม่
Phase 1 ใช้ revocation list แบบ local เท่านั้น (ไม่มีการกระจายอัตโนมัติ เพราะไม่มี network transport)
identity ที่ถูก revoke แล้ว **สร้าง session ใหม่ไม่ได้** แต่ session เก่ายังถอดได้ตามปกติ

---

## 4. โหมด authentication

### 4.1 `AUTH_IMPLICIT` — ค่าเริ่มต้น overhead 0 byte

ยืมแนวคิด auth mode ของ HPKE: เพิ่ม DH ระหว่าง **static key ของผู้ส่ง** กับ **static key ของผู้รับ** เข้าไปในการ derive

```
dh_ephemeral = X25519(eph_sender_sk,    recipient.x25519_static_pk)
dh_static    = X25519(static_sender_sk, recipient.x25519_static_pk)
ss_mlkem     = ML-KEM-768.Encap(recipient.mlkem_static_pk)
```

ผู้ที่ไม่มี `static_sender_sk` คำนวณ `dh_static` ไม่ได้ จึง derive session key ไม่ได้
**ได้ sender authentication มาโดยไม่เสีย byte เพิ่มเลยแม้แต่ตัวเดียว**

### 4.2 `AUTH_PQ_EXPLICIT` — ทางเลือก overhead 3,373 B

เพิ่มลายเซ็นบน transcript

```
signature = Ed25519.Sign(ed25519_sk, transcript) || ML-DSA-65.Sign(mldsa_sk, transcript)
            (64 B)                                  (3,309 B)
```

**ต้องผ่านทั้งคู่จึงนับว่าถูก** ถ้าอันใดอันหนึ่งไม่ผ่าน = ปฏิเสธทั้ง session
ใช้เมื่อ envelope เป็น external (ไม่กินความจุของภาพ) หรือเมื่อต้องการ non-repudiation

### 4.3 ข้อจำกัดที่ต้องประกาศ

`AUTH_IMPLICIT` ให้ **การพิสูจน์ตัวตนเชิงคลาสสิกเท่านั้น**
ผู้โจมตีที่มี quantum computer ในอนาคตจะแกะ X25519 ได้ จึงปลอมตัวเป็นผู้ส่งได้
**แต่ยังถอดข้อความที่ดักไว้วันนี้ไม่ได้** เพราะ confidentiality มาจาก ML-KEM

ทำไมยอมรับได้สำหรับ threat model นี้:

| | การปลอมตัว | การถอดรหัส |
|---|---|---|
| ต้องทำเมื่อไหร่ | **ตอนนั้น** (online) — ต้องมี quantum computer ณ เวลาที่ session ถูกสร้าง | **ย้อนหลังได้** (offline) — เก็บวันนี้ ถอดปีหน้า |
| ภัยที่เราต้องกัน | ต่ำ | **สูง (T4 harvest now decrypt later)** |
| ระบบนี้กันได้ไหม | ไม่ ใน `AUTH_IMPLICIT` | **ได้** |

การไม่มี PQ authentication แบบ non-interactive โดยไม่ใช้ signature เป็น **ข้อจำกัดของ ML-KEM เอง** ไม่ใช่ของการออกแบบนี้ — ML-KEM ไม่รองรับ static-static แบบที่ DH ทำได้ (`THREAT_MODEL.md` G5)

---

## 5. Transcript

### 5.1 Length-prefix

```
LP(x) = uint16_be(len(x)) || x
```

ทุกฟิลด์ที่ต่อเข้า transcript ต้องผ่าน `LP()` **ไม่มีข้อยกเว้น**

**เหตุผล:** ถ้าต่อกันตรงๆ `A || BC` กับ `AB || C` จะได้ผลลัพธ์เดียวกัน
ผู้โจมตีที่ควบคุมความยาวของบางฟิลด์ได้ สามารถทำให้ transcript สองชุดที่มีความหมายต่างกันมีค่าเท่ากัน แล้วย้ายความหมายของฟิลด์ได้ — เรียกว่า canonicalization attack
ฟิลด์ที่ยาวคงที่ก็ต้อง `LP()` เหมือนกัน เพื่อไม่ต้องมาคิดทีหลังว่าอันไหนคงที่อันไหนไม่

### 5.2 สูตร

**ลำดับตายตัว ห้ามสลับ ห้ามเพิ่ม ห้ามลด**

```
transcript = LP("SIENG3-transcript-v1")        // domain separator
          || LP(uint8(version))
          || LP(uint8(suite))
          || LP(uint8(auth_mode))
          || LP(session_id)                    // 4 B
          || LP(sender.fingerprint)            // 32 B
          || LP(recipient.fingerprint)         // 32 B
          || LP(sender.x25519_static_pk)       // 32 B
          || LP(sender.mlkem_static_pk)        // 1184 B
          || LP(recipient.x25519_static_pk)    // 32 B
          || LP(recipient.mlkem_static_pk)     // 1184 B
          || LP(eph_x25519_pk)                 // 32 B
          || LP(mlkem_ciphertext)              // 1088 B
```

**ทำไมต้องมี pk ของทั้งสองฝั่งอยู่ใน transcript ทั้งที่ต่างฝ่ายต่างรู้อยู่แล้ว**
เพราะ transcript คือสิ่งที่ผูก session key เข้ากับ *การแลกเปลี่ยนครั้งนี้ครั้งเดียว*
ถ้า pk ไม่อยู่ในนั้น ผู้โจมตีที่สลับ pk ระหว่างทางจะไม่ถูกจับได้จากการที่ session key ไม่ตรงกัน

**ทำไมต้องมี `mlkem_ciphertext`**
ML-KEM ไม่เป็น committing โดยตัวมันเอง — ciphertext ต่างกันอาจ decapsulate ได้ shared secret เดียวกันในบางสถานการณ์
การผูก ct เข้า transcript ปิดช่องนี้

---

## 6. Handshake

### 6.1 ก่อนเริ่ม

| ฝ่าย | ต้องมีอะไรอยู่แล้ว |
|---|---|
| ผู้ส่ง | `IdentitySecret` ของตัวเอง · `Identity` ของผู้รับที่ **ผ่านการเทียบ fingerprint แล้ว** (§3.3) |
| ผู้รับ | `IdentitySecret` ของตัวเอง · `Identity` ของผู้ส่งที่ผ่านการเทียบแล้ว |

ถ้า `Identity` ของอีกฝ่ายยังไม่ได้ผ่านการเทียบ **ต้องปฏิเสธการสร้าง session** ไม่ใช่เตือนแล้วทำต่อ

### 6.2 ฝั่งผู้ส่ง

```
ขั้น 1  ตรวจสิทธิ์
        - recipient อยู่ใน TrustStore และ verified_via ไม่ใช่ค่าว่าง
        - recipient ไม่อยู่ใน revocation list
        ไม่ผ่าน -> ยกเลิก ไม่มีการ fallback

ขั้น 2  สุ่มค่า
        session_id  = random(4 B)
        eph_x25519  = X25519.GenerateKeypair()

ขั้น 3  ทำ KEM
        dh_ephemeral = X25519(eph_x25519.sk,    recipient.x25519_static_pk)   // 32 B
        dh_static    = X25519(static_sender_sk, recipient.x25519_static_pk)   // 32 B
        (mlkem_ct, ss_mlkem) = ML-KEM-768.Encap(recipient.mlkem_static_pk)

ขั้น 4  ประกอบ transcript ตาม 5.2

ขั้น 5  derive shared secret
        ss = HKDF-SHA256(
               salt = "",
               ikm  = LP(dh_ephemeral) || LP(dh_static) || LP(ss_mlkem) || LP(transcript),
               info = "sieng3/kem/x25519-mlkem768/v1",
               len  = 32)
        zeroize dh_ephemeral, dh_static, ss_mlkem, eph_x25519.sk

ขั้น 6  ถ้า auth_mode = AUTH_PQ_EXPLICIT
        signature = Ed25519.Sign(...) || ML-DSA-65.Sign(...)   บน transcript

ขั้น 7  สร้าง SessionEnvelope (รายละเอียด FORMAT_SPEC.md 4)
        เลือกโหมดด้วย choose_mode(carrier, payload_rate, auth_mode)

ขั้น 8  derive คีย์ระดับ session
        K_hdr_session = HKDF-Expand(ss, "sieng3/hdrkey/v1", 32)
        CK[0]         = HKDF-Expand(ss, "sieng3/chain/v1",  32)
        zeroize ss

ขั้น 9  เซฟ ratchet state (lock -> generation+1 -> atomic commit)
        ต้องเสร็จก่อนเขียนไฟล์ stego เสมอ
```

**สิ่งที่ผู้ส่งรู้หลังจบ:** `K_hdr_session`, `CK[0]`, `session_id` · **ไม่รู้** ว่าผู้รับได้รับหรือยัง (ไม่มี round trip)

### 6.3 ฝั่งผู้รับ

```
ขั้น 1  อ่าน SessionEnvelope
        external -> จากไฟล์ .sess
        inline   -> ถอดจากภาพก่อน แล้วค่อยอ่าน header

ขั้น 2  ตรวจ version กับ suite ว่ารองรับ  ไม่รองรับ -> ปฏิเสธ

ขั้น 3  ตรวจสิทธิ์
        - sender_fingerprint อยู่ใน TrustStore และผ่านการเทียบแล้ว
        - sender ไม่อยู่ใน revocation list
        ไม่ผ่าน -> ยกเลิก

ขั้น 4  ทำ KEM ฝั่งตรงข้าม
        dh_ephemeral = X25519(x25519_static_sk, envelope.eph_x25519_pk)
        dh_static    = X25519(x25519_static_sk, sender.x25519_static_pk)
        ss_mlkem     = ML-KEM-768.Decap(mlkem_static_sk, envelope.mlkem_ct)

ขั้น 5  ประกอบ transcript เองจากค่าที่มี ตาม 5.2 (ห้ามเชื่อ transcript ที่ส่งมา)

ขั้น 6  ถ้า auth_mode = AUTH_PQ_EXPLICIT
        verify Ed25519 และ ML-DSA-65 -> ต้องผ่านทั้งคู่ ไม่ผ่าน -> ยกเลิก

ขั้น 7  derive ss ด้วยสูตรเดียวกับขั้น 5 ของผู้ส่ง
        ถ้า MITM สลับ pk มา ค่าที่ได้จะไม่ตรง -> ถอด header ไม่ออก -> ปฏิเสธ

ขั้น 8  derive K_hdr_session และ CK[0] เหมือนกัน

ขั้น 9  ถอด header ด้วย K_hdr_session -> ได้ ctr -> ratchet ไปที่ ctr -> ถอด payload
```

**การพิสูจน์ตัวตนใน `AUTH_IMPLICIT` เกิดขึ้นโดยปริยายที่ขั้น 7** — ไม่มีขั้นตอน verify แยก
ถ้าผู้ส่งไม่ใช่ตัวจริง `dh_static` จะไม่ตรง `ss` จะไม่ตรง และทุกอย่างหลังจากนั้นจะถอดไม่ออก

### 6.4 ทำไม `K_hdr_session` ต้องมาจาก `ss` ไม่ใช่จาก `MK[n]`

**วงจรไก่กับไข่** — header บรรจุ `ctr` แต่การจะหา `MK[ctr]` ได้ต้องรู้ `ctr` ก่อน ซึ่งอยู่ใน header ที่ถูก whiten อยู่

ทางแก้: whiten header ด้วยคีย์ระดับ **session** ที่ derive จาก `ss` โดยตรง
ผู้รับมี `ss` ตั้งแต่จบขั้น 7 จึงถอด header ได้ทันทีโดยไม่ต้องรู้ `ctr` แล้วค่อย ratchet ตามไป

**สิ่งที่ต้องยอมรับ:** `K_hdr_session` ไม่ ratchet ตามข้อความ ทุก header ในทั้ง session ใช้คีย์เดียวกัน
จึงต้องใส่ `ctr` เข้าไปใน keystream ของ whitening เพื่อให้ keystream ต่างกันทุกข้อความ (ดู `FORMAT_SPEC.md` §3.3)

---

## 7. Session ที่ใช้รหัสผ่านแทน identity

โหมดสำรองสำหรับกรณีที่ยังไม่ได้แลก identity กัน

```
ss = Argon2id(password, salt, t=3, m=64MiB, p=4, len=32)
```

| | |
|---|---|
| ได้อะไร | confidentiality · integrity · forward secrecy (ratchet ทำงานเหมือนเดิม) |
| **ไม่ได้อะไร** | **sender authentication** และ **post-quantum confidentiality** |
| ควรใช้เมื่อไหร่ | ทดสอบ · ส่งให้ตัวเอง · กรณีที่ยอมรับความเสี่ยงได้แล้ว |
| UI ต้องทำอะไร | แสดงชัดว่าโหมดนี้ไม่มี authentication และไม่ทน quantum |

`suite` ในhead เป็นคนละค่ากับโหมด identity ผู้รับจึงรู้ทันทีว่าไฟล์นี้มาจากโหมดไหน

---

## 8. Session lifetime

| เหตุการณ์ | ทำอะไร |
|---|---|
| ส่งครบ 2²⁴ − 1 ข้อความ | ต้องสร้าง session ใหม่ · counter เต็ม 24 bit แล้ว |
| ผู้ใช้สั่งจบ session | `destroy_session(sid)` ลบ state + skipped key pool + cache แล้วคืน report |
| identity ถูก revoke | session ที่มีอยู่ยังถอดได้ · สร้างใหม่ไม่ได้ |
| ตรวจพบ rollback | `policy="abort"` (ค่าเริ่มต้น) หยุดทันที · `"rekey"` สร้าง session ใหม่ · `"warn"` ต้องเปิดใช้แบบตั้งใจและเตือนใน UI ทุกครั้ง |
| **ครบรอบ re-KEM** | **Phase 2** — ยังไม่มีใน Phase 1 จึงไม่มี PCS (`THREAT_MODEL.md` G1) |

---

## 9. สิ่งที่ implementation ต้องทำและห้ามทำ

| ต้องทำ | เหตุผล |
|---|---|
| ประกอบ transcript ขึ้นมาเองทั้งสองฝั่ง | เชื่อ transcript ที่ส่งมา = ยกเลิกการป้องกัน MITM ทั้งหมด |
| `LP()` ทุกฟิลด์ | กัน canonicalization attack |
| zeroize `dh_*`, `ss_mlkem`, `ss`, `eph_sk` ทันทีที่ใช้เสร็จ | ลดหน้าต่างเวลาที่คีย์อยู่ในหน่วยความจำ |
| เซฟ ratchet state **ก่อน** เขียนไฟล์ stego | ยอมข้าม counter ดีกว่าใช้ซ้ำ |
| ปฏิเสธเมื่อ identity ยังไม่ผ่านการเทียบ fingerprint | สมมติฐาน A-1 |
| ตรวจ revocation ก่อนสร้าง session ทุกครั้ง | S6 |

| ห้ามทำ | เหตุผล |
|---|---|
| ห้าม implement ML-KEM หรือ ML-DSA เอง | ใช้ไลบรารีที่ผ่านการตรวจแล้วเท่านั้น |
| ห้ามมีปุ่ม "ข้ามการยืนยัน fingerprint" | ผู้ใช้จะกดผ่านทุกครั้ง |
| ห้ามแยกสาเหตุใน error ของการถอดรหัส | error เดียว เวลาเท่ากัน ไม่บอกว่าผิดที่ signature หรือ AEAD |
| ห้าม fallback ไป `AUTH_IMPLICIT` เมื่อ `AUTH_PQ_EXPLICIT` ล้มเหลว | downgrade attack |
| ห้ามใช้ suite เดิมซ้ำเมื่อเปลี่ยนสูตร | ขึ้นเลข suite เสมอ (`PROJECT_STRUCTURE.md` §8.4) |

---

## 10. Test ที่ผูกกับเอกสารนี้

| Test | ตรวจอะไร | เฟส |
|---|---|:---:|
| `test_mitm_key_substitution_is_rejected` | สลับ pk ผู้รับ -> `ss` ไม่ตรง -> ถอดไม่ออก | 7.3 |
| `test_transcript_canonicalization` | `A‖BC` กับ `AB‖C` ต้องได้ transcript คนละค่า | 7.3 |
| `test_revoked_identity_is_refused` | identity ที่ revoke แล้วสร้าง session ใหม่ไม่ได้ | 7.3 |
| `test_unverified_identity_is_refused` | identity ที่ยังไม่ผ่านการเทียบ fingerprint ใช้ไม่ได้ | 7.3 |
| `test_partial_signature_is_rejected` | Ed25519 ผ่านแต่ ML-DSA ไม่ผ่าน -> ปฏิเสธ | 7.3 |
| `test_no_downgrade_to_implicit` | `AUTH_PQ_EXPLICIT` ล้มเหลวแล้วห้าม fallback | 7.3 |
| `test_password_mode_declares_no_authentication` | โหมดรหัสผ่านต้องรายงานว่าไม่มี authentication | 7.6 |
| KAT ของ X25519 · ML-KEM-768 · ML-DSA-65 · HKDF | ตรงกับ reference vector ทุก bit | 7.1 · 7.2 · 7.3 |
