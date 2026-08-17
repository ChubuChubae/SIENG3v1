# SIENG3 — Format Specification

> ทุก bit ที่ระบบนี้ผลิต กำหนดไว้ที่นี่
> เกณฑ์ของเอกสารนี้: **เขียน pseudo-code เดินตามได้จนจบโดยไม่ต้องเดาอะไรเลย**
> เวอร์ชัน 1.0 · Phase 1.3 · ขึ้นกับ `SESSION_PROTOCOL.md` · suite `x25519-mlkem768-gcmsiv/v1`

---

## 1. ข้อตกลงพื้นฐาน

| หัวข้อ | ค่า |
|---|---|
| Endianness | **big-endian** ทุกที่ ไม่มีข้อยกเว้น |
| Length-prefix | `LP(x) = uint16_be(len(x)) || x` |
| Hash | SHA-256 |
| KDF | HKDF-SHA256 (RFC 5869) |
| AEAD | AES-256-GCM-SIV (RFC 8452) |
| Bit order ตอนฝัง | MSB first ภายในแต่ละ byte |
| `version` ปัจจุบัน | `1` |
| `suite` ปัจจุบัน | `1` = `x25519-mlkem768-gcmsiv/v1` |

**กฎการขึ้นเวอร์ชัน:** แก้สูตร derive · แก้ layout · แก้ label string → **ขึ้น `suite` ใหม่เสมอ**
แก้ของเดิมทับลงไป = ไฟล์ที่ฝังไว้แล้วทั้งหมดถอดไม่ได้อีกเลย

---

## 2. ลำดับการ derive คีย์ทั้งหมด

### 2.1 แผนภาพรวม

```
dh_ephemeral (32) ─┐
dh_static    (32) ─┼─► HKDF ─► ss (32) ─┬─► HKDF ─► K_hdr_session (32)
ss_mlkem     (32) ─┤   "kem"            │   "hdrkey"
transcript        ─┘                    │
                                        └─► HKDF ─► CK[0] (32)
                                            "chain"        │
                                                           ├─► HKDF ─► MK[n] (32) ─► expand ─┬─ K_aead   (32)
                                                           │   "msg"                         ├─ nonce    (12)
                                                           │                                 ├─ K_hdr    (32)  ยังไม่ใช้ใน v1
                                                           └─► HKDF ─► CK[n+1] (32)          └─ seed_sel (32)
                                                               "ratchet"
                                                               แล้ว zeroize CK[n] ทันที
```

### 2.2 Label string ทั้งหมด

รวมไว้ที่เดียวใน `crypto/kdf/labels.py` ห้ามเขียน string ตรงๆ ที่อื่น

| ค่าคงที่ | Label | ใช้กับ |
|---|---|---|
| `KEM_SUITE` | `sieng3/kem/x25519-mlkem768/v1` | derive `ss` |
| `HEADER_KEY` | `sieng3/hdrkey/v1` | derive `K_hdr_session` จาก `ss` |
| `CHAIN_INIT` | `sieng3/chain/v1` | derive `CK[0]` จาก `ss` |
| `RATCHET_STEP` | `sieng3/ratchet/v1` | `CK[n]` → `CK[n+1]` |
| `MESSAGE_KEY` | `sieng3/msg/v1` | `CK[n]` → `MK[n]` |
| `MESSAGE_KEYS` | `sieng3/msgkeys/v1` | `MK[n]` → คีย์ย่อย 4 ตัว |
| `HEADER_STREAM` | `sieng3/hdrstream/v1` | keystream สำหรับ whiten header |
| `TRANSCRIPT` | `SIENG3-transcript-v1` | domain separator ของ transcript |
| `KEYSTORE_WRAP` | `sieng3/keystore/v1` | ห่อ private key ตอนเก็บลงดิสก์ |
| `STATE_WRAP` | `sieng3/state/v1` | เข้ารหัสไฟล์ ratchet state |

### 2.3 สูตรเต็ม

```
// --- ระดับ session ---------------------------------------------------------
ss = HKDF(salt = "",
          ikm  = LP(dh_ephemeral) || LP(dh_static) || LP(ss_mlkem) || LP(transcript),
          info = KEM_SUITE,  len = 32)

K_hdr_session = HKDF-Expand(ss, HEADER_KEY, 32)
CK[0]         = HKDF-Expand(ss, CHAIN_INIT, 32)
// zeroize ss หลังจากนี้

// --- ระดับข้อความ ----------------------------------------------------------
MK[n]   = HKDF-Expand(CK[n], MESSAGE_KEY,  32)
CK[n+1] = HKDF-Expand(CK[n], RATCHET_STEP, 32)
// zeroize CK[n] ทันทีหลังคำนวณสองบรรทัดบน

okm = HKDF-Expand(MK[n],
                  info = MESSAGE_KEYS || sid(4) || ctr_be24(3),
                  len  = 108)
K_aead   = okm[  0 :  32]
nonce    = okm[ 32 :  44]
K_hdr    = okm[ 44 :  76]    // สำรองไว้ ยังไม่ใช้ใน v1 (ดู 3.3)
seed_sel = okm[ 76 : 108]
// zeroize MK[n] หลังจากนี้
```

**`seed_sel` คือตัวที่ทำให้เรื่องนี้เป็น steganography ไม่ใช่แค่ encryption**
มันกำหนด permutation ลับของการไล่ coefficient ถ้าไม่มี ผู้ตรวจรู้ลำดับ scan ที่แน่นอน
พอมันมาจาก `MK[n]` แปลว่า **ทุกภาพมี selection channel คนละอัน** ความรู้ที่ได้จากภาพหนึ่งใช้กับภาพถัดไปไม่ได้

---

## 3. Header

### 3.1 ขนาด — ตัดสินใจแล้วว่า 12 B

| ทางเลือก | ขนาด | ที่ 0.05 bpnzAC (163 B) | ที่ 0.1 bpnzAC (325 B) |
|---|---:|---:|---:|
| **12 B (เลือกแบบนี้)** | 96 bit | 7.4% ของความจุ | 3.7% |
| 16 B (มี carrier binding tag) | 128 bit | 9.8% | 4.9% |

**เหตุผลที่เลือก 12 B:** binding tag 4 B ใน header **ซ้ำซ้อน** เพราะ AAD ผูกกับ `carrier.fingerprint()` เต็มรูปอยู่แล้ว (§5.2)
สิ่งที่ tag ให้เพิ่มคือการรู้เร็วขึ้นว่าเป็นไฟล์ผิดก่อนจะเสียเวลารัน STC extract — เป็น optimization ไม่ใช่ความปลอดภัย
และการปฏิเสธจาก header ที่ parse ไม่ผ่านก็เร็วอยู่แล้ว จึงไม่คุ้มกับความจุที่เสียไป 33%

### 3.2 Layout ระดับ bit

```
byte  0    1    2    3    4    5    6    7    8    9   10   11
    +----+----+----+----+----+----+----+----+----+----+----+----+
    | vs |      session id       |    counter   |    length    | fl |
    +----+----+----+----+----+----+----+----+----+----+----+----+

byte 0      bit 7-4  version   (4 bit)  ปัจจุบัน = 1
            bit 3-0  suite     (4 bit)  ปัจจุบัน = 1
byte 1-4    session id         (32 bit) สุ่มตอนสร้าง session
byte 5-7    counter            (24 bit) ลำดับข้อความใน session, เริ่มที่ 0
byte 8-10   ciphertext length  (24 bit) หน่วยเป็น byte, สูงสุด 16,777,215
byte 11     flags              (8 bit)  ดู 3.4
```

**ทั้ง 12 byte ถูก whiten ก่อนนำไปฝัง** ดู §3.3

### 3.3 Whitening

```
keystream = HKDF-Expand(K_hdr_session,
                        info = HEADER_STREAM || ctr_be24(3),
                        len  = 12)
header_on_wire = header_plaintext XOR keystream
```

| ประเด็น | คำอธิบาย |
|---|---|
| ทำไมต้อง whiten | `version` `suite` `flags` เป็นค่าที่เดาได้ ถ้าไม่ whiten จะมี bit pattern คงที่ทุกไฟล์ ซึ่งเป็นสิ่งที่ steganalyst ยึดได้ทันที |
| ทำไมใช้คีย์ระดับ session | วงจรไก่กับไข่ — ต้องรู้ `ctr` ถึงจะหา `MK[ctr]` ได้ แต่ `ctr` อยู่ใน header (`SESSION_PROTOCOL.md` §6.4) |
| ทำไมต้องใส่ `ctr` ใน info | `K_hdr_session` เหมือนกันทั้ง session ถ้าไม่ใส่ `ctr` keystream จะซ้ำทุกข้อความ แล้ว XOR สอง header เข้าด้วยกันจะเห็นความต่างของ plaintext |
| แล้วผู้รับหา `ctr` ได้ยังไงถ้า keystream ขึ้นกับ `ctr` | **ลองไล่จาก `ctr` ที่คาดไว้** — ผู้รับรู้ `ctr` ล่าสุดที่เห็น จึงลองตั้งแต่ตัวนั้นไปข้างหน้าจนถึง `max_ratchet_skip` ตัวที่ parse แล้วได้ `version`/`suite` ที่รู้จักและ `length` สมเหตุสมผลคือตัวที่ถูก |
| ถ้าไม่มีตัวไหน parse ผ่าน | ปฏิเสธด้วย `DecryptError` ข้อความเดียวกับทุกกรณี |

> **ข้อควรระวังตอน implement:** การไล่ `ctr` ต้องมีเพดานตาม `settings.max_ratchet_skip` เสมอ
> ไม่งั้นไฟล์ที่ไม่มีข้อมูลอยู่เลยจะทำให้ระบบวนคำนวณ HKDF จนกว่าจะครบ 2²⁴ รอบ

### 3.4 Flags

```
bit 0   has_precover        1 = ฝังด้วย SI-UNIWARD (มีภาพก่อนบีบอัด)
bit 1   multipart           1 = payload ถูกแบ่งข้ามหลายไฟล์
bit 2-3 envelope mode       00 = EXTERNAL   01 = INLINE   10 = MULTIPART   11 = สงวน
bit 4   auth mode           0 = AUTH_IMPLICIT   1 = AUTH_PQ_EXPLICIT
bit 5   session bootstrap   1 = ไฟล์นี้บรรจุ SessionEnvelope ด้วย
bit 6-7 สงวน                ต้องเป็น 0 -- ผู้รับต้องปฏิเสธถ้าไม่ใช่
```

**ทำไม bit สงวนต้องเป็น 0 และต้องตรวจ:** ถ้าปล่อยผ่าน ผู้โจมตีใช้ bit พวกนี้เป็นช่องส่งข้อมูลลอดออกไปได้ และเวอร์ชันอนาคตจะแยกไม่ออกว่าเป็นของเก่าหรือของที่ถูกดัดแปลง

---

## 4. SessionEnvelope

### 4.1 โครงสร้าง

```
โหมด EXTERNAL (ไฟล์ <sid>.sess)
+-------------------------------+--------+
| magic  "SI3S"                 |    4 B |   มีได้เพราะเป็นไฟล์แยก ไม่ได้ฝังในภาพ
| version                       |    1 B |
| suite                         |    1 B |
| auth_mode                     |    1 B |
| envelope_mode                 |    1 B |
| session_id                    |    4 B |
| sender_fingerprint            |   32 B |
| recipient_fingerprint         |   32 B |
| eph_x25519_pk                 |   32 B |
| mlkem_ciphertext              | 1088 B |
| signature (ถ้า auth = PQ)      | 3373 B |
+-------------------------------+--------+
รวม  1,196 B (implicit)  /  4,569 B (explicit)

โหมด INLINE (ฝังในภาพ)
โครงเดียวกัน แต่ตัด magic 4 B ออก แล้ว whiten ทั้งก้อนเหมือน header
รวม  1,192 B (implicit)  /  4,565 B (explicit)
```

### 4.2 ทำไม external มี magic ได้แต่ inline มีไม่ได้

ไฟล์ `.sess` เป็นไฟล์แยกที่ไม่ได้ซ่อนอยู่ในอะไร magic ช่วยให้ตรวจชนิดไฟล์ได้เร็วและถูกต้อง
ส่วนสิ่งที่ฝังในภาพ **ห้ามมีโครงสร้างใดๆ เด็ดขาด** ทุก bit ต้องแยกจากค่าสุ่มไม่ออก

**แต่การมีไฟล์ `.sess` วางอยู่ก็เป็นหลักฐานในตัวมันเองว่ามีการใช้ระบบนี้**
ผู้ใช้ต้องรู้เรื่องนี้ และ `INLINE` มีไว้สำหรับกรณีที่ต้องการหลีกเลี่ยงจุดนี้ แลกกับความจุ

### 4.3 เกณฑ์ของ `choose_mode()`

```python
def choose_mode(carrier, payload_rate, auth_mode):
    """เลือกโหมด envelope จากความจุจริงของพาหะ ไม่ใช่จากความชอบของผู้ใช้"""
    capacity_bits = carrier.nnz_ac() * payload_rate
    envelope_bits = envelope_size(auth_mode) * 8

    if capacity_bits >= envelope_bits * 8:      # เหลือที่ให้ payload อย่างน้อย 7 เท่า
        return ENVELOPE_INLINE
    if capacity_bits >= envelope_bits * 8 / expected_file_count:
        return ENVELOPE_MULTIPART
    return ENVELOPE_EXTERNAL
```

ตารางผลลัพธ์จริง (auth = `AUTH_IMPLICIT`, envelope 1,192 B = 9,536 bit)

| พาหะ | nnzAC โดยประมาณ | ที่ 0.1 bpnzAC | โหมดที่ได้ |
|---|---:|---:|---|
| 512×512 QF75 (ภาพงานวิจัย) | 26,000 | 2,600 bit | **EXTERNAL** |
| 1024×1024 QF85 | 130,000 | 13,000 bit | **EXTERNAL** (ยังไม่ถึง 8 เท่า) |
| 2048×1536 QF90 (ภาพมือถือ) | 500,000 | 50,000 bit | **INLINE** |
| 4000×3000 QF90 (ภาพกล้อง) | 1,500,000 | 150,000 bit | **INLINE** |

**ค่าเริ่มต้นของงานวิจัยจึงเป็น `EXTERNAL` เสมอ** ผู้ใช้ override ได้แต่ระบบต้องเตือนเมื่อการเลือกทำให้ payload rate จริงพุ่งขึ้น

---

## 5. โครงสร้างสิ่งที่ฝังลงในภาพ

### 5.1 ลำดับ bit

```
[ header 12 B (whitened) ] [ ciphertext + AEAD tag  length B ]
     96 bit                       length * 8 bit

ถ้า flag session bootstrap = 1
[ envelope (whitened) ] [ header 12 B (whitened) ] [ ciphertext + tag ]
```

ทั้งหมดถูกต่อเป็น bit stream เดียวแล้วส่งเข้า `coder/stc.embed()` พร้อมกัน
**ไม่มีการแบ่งเป็นสองรอบ** เพราะจะทำให้เกิดสองบริเวณที่มีสถิติต่างกันในภาพ

### 5.2 AAD

```
aad = header_plaintext(12 B) || carrier.fingerprint()(32 B)
```

**ใช้ header ที่ยังไม่ whiten** เพราะผู้รับ unwhiten ก่อนแล้วจึงเรียก AEAD open

`carrier.fingerprint()` ของ JPEG:

```
SHA-256( LP(quant_tables_flat) || LP(uint16_be(width)) || LP(uint16_be(height))
      || LP(subsampling)       || LP(uint8(n_components)) || LP(uint8(progressive)) )
```

**ต้องประกอบจากสิ่งที่ไม่เปลี่ยนตอนฝังเท่านั้น** — ห้ามใส่ค่า coefficient เข้าไปเด็ดขาด ไม่งั้นผู้รับคำนวณค่าเดิมไม่ได้

ผลที่ได้: ciphertext ที่ถูกตัดไปแปะภาพอื่นจะ **ถอดไม่ผ่าน** เพราะ AAD ไม่ตรง (`THREAT_MODEL.md` S10)

### 5.3 AEAD

```
ciphertext_with_tag = AES-256-GCM-SIV.Seal(K_aead, nonce, payload, aad)
```

tag 16 B อยู่ท้าย ciphertext แล้ว `length` ใน header นับรวม tag ด้วย

---

## 6. ไฟล์ ratchet state

```
+-------------------------------+--------+
| magic  "SI3T"                 |    4 B |
| version                       |    1 B |
| nonce                         |   12 B |
| ciphertext + tag              |    var |
+-------------------------------+--------+

plaintext ข้างใน (เข้ารหัสด้วย AEAD, คีย์มาจาก Argon2id(รหัสผ่านของ keystore))
+-------------------------------+--------+
| generation                    |    8 B |  monotonic, เพิ่มอย่างเดียว
| machine_id                    |   16 B |  ตรวจว่าถูกคัดลอกข้ามเครื่อง
| session_id                    |    4 B |
| chain_key ปัจจุบัน             |   32 B |
| counter ปัจจุบัน               |    3 B |
| จำนวน skipped key             |    2 B |
| skipped keys [ctr(3) key(32)] |    var |  จำกัดตาม max_ratchet_skip
| consumed counter bitmap        |    var |  กัน replay
+-------------------------------+--------+
```

**ลำดับการเขียนที่ถูกต้อง** (ผิดลำดับ = counter ซ้ำได้)

```
1. acquire exclusive lock          <- ล็อกก่อน load ไม่ใช่ก่อน save
2. load state + ตรวจ generation ไม่ลดลง และ machine_id ตรง
3. ratchet -> ได้ MK[n], generation + 1
4. เขียน state: temp -> fsync(temp) -> rename -> fsync(dir)
5. เขียนไฟล์ stego                 <- หลังจาก state ลงดิสก์แล้วเท่านั้น
6. release lock
```

ตายระหว่างขั้น 4-5 = counter ถูกข้ามไปหนึ่งตัวโดยไม่มีไฟล์ออกมา — **เสียของ แต่ไม่เสียความปลอดภัย**

---

## 7. Pseudo-code เดินตามได้จนจบ

### 7.1 Embed

```python
carrier = open_carrier(cover_path)                    # sniff magic, ไม่เชื่อนามสกุล
planes  = carrier.planes()
plane   = planes[0]                                   # Y component

with StateLock():
    state = state_store.load()
    verify_monotonic(state, last_seen_generation)
    keys = SendChain(state).next_message_keys()       # K_aead, nonce, seed_sel, ctr
    state_store.save(state.advance())                 # ขั้น 4 ของ 6

header = Header(version=1, suite=1, sid=state.sid, counter=keys.counter,
                length=len(payload) + 16, flags=build_flags(...))
aad    = header.pack() + carrier.fingerprint()
ct     = gcm_siv.seal(keys.aead, keys.nonce, payload, aad)

header = header.with_length(len(ct))                  # length นับรวม tag
aad    = header.pack() + carrier.fingerprint()        # ประกอบใหม่หลังรู้ length จริง
ct     = gcm_siv.seal(keys.aead, keys.nonce, payload, aad)

bits   = to_bits(whiten(header.pack(), k_hdr_session, keys.counter)) + to_bits(ct)
if flags.session_bootstrap:
    bits = to_bits(whiten(envelope.pack_inline(), k_hdr_session, 0)) + bits

order  = permute(plane.n_changeable(), keys.seed_sel)
rho_p1, rho_m1 = JUniwardCost().costs(carrier, plane)
values = stc.embed(plane.values[order], rho_p1[order], rho_m1[order], bits, h=10)

plane.values[order] = values
carrier.apply(planes)
carrier.save(output_path)                             # ขั้น 5
```

> **จุดที่ต้องระวัง:** `length` ใน header ต้องเป็นความยาวของ ciphertext จริง แต่ AAD ก็มี header อยู่ข้างใน
> จึงต้อง seal สองรอบตามโค้ดข้างบน หรือคำนวณ `len(payload) + 16` ล่วงหน้าให้ถูกตั้งแต่แรก
> (GCM-SIV ให้ ciphertext ยาวเท่า plaintext + tag 16 B เสมอ จึงคำนวณล่วงหน้าได้ และควรทำแบบนั้น)

### 7.2 Extract

```python
carrier = open_carrier(stego_path)
plane   = carrier.planes()[0]

envelope = load_envelope(sess_path) if external else None
ss       = derive_ss_from_envelope(envelope, my_identity)   # SESSION_PROTOCOL 6.3
k_hdr_session = hkdf_expand(ss, HEADER_KEY, 32)

for candidate_ctr in range(last_seen, last_seen + settings.max_ratchet_skip):
    keys   = RecvChain(state).keys_for(candidate_ctr)
    order  = permute(plane.n_changeable(), keys.seed_sel)
    raw    = stc.extract(plane.values[order], HEADER_BITS, h=10)
    header = Header.unpack(unwhiten(raw, k_hdr_session, candidate_ctr))
    if header.version == 1 and header.suite == 1 and header.flags_reserved_are_zero():
        break
else:
    raise DecryptError()                              # ข้อความเดียว เวลาเท่ากัน

ct  = from_bits(stc.extract(plane.values[order], HEADER_BITS + header.length * 8, h=10))
aad = header.pack() + carrier.fingerprint()
payload = gcm_siv.open(keys.aead, keys.nonce, ct[HEADER_BYTES:], aad)

state.mark_consumed(header.counter)
state_store.save(state)
```

---

## 8. สรุปค่าคงที่

| ค่า | ค่าที่ใช้ |
|---|---:|
| `HEADER_BYTES` | 12 |
| `HEADER_BITS` | 96 |
| `AEAD_TAG_BYTES` | 16 |
| `AEAD_NONCE_BYTES` | 12 |
| `AEAD_KEY_BYTES` | 32 |
| `SESSION_ID_BYTES` | 4 |
| `COUNTER_BITS` | 24 |
| `LENGTH_BITS` | 24 |
| `FINGERPRINT_BYTES` | 32 |
| `ENVELOPE_EXTERNAL_IMPLICIT` | 1,196 |
| `ENVELOPE_EXTERNAL_EXPLICIT` | 4,569 |
| `ENVELOPE_INLINE_IMPLICIT` | 1,192 |
| `ENVELOPE_INLINE_EXPLICIT` | 4,565 |
| `MAX_CIPHERTEXT_BYTES` | 16,777,215 |
| `MAX_MESSAGES_PER_SESSION` | 16,777,215 |

---

## 9. Test ที่ผูกกับเอกสารนี้

| Test | ตรวจอะไร | เฟส |
|---|---|:---:|
| `test_header_roundtrip` | pack แล้ว unpack ได้ค่าเดิมทุกฟิลด์ | 7.5 |
| `test_header_bits_are_indistinguishable_from_random` | 10,000 header จาก session ต่างกัน ผ่าน monobit + runs test | 7.5 |
| `test_reserved_flags_must_be_zero` | bit 6-7 ไม่ใช่ 0 → ปฏิเสธ | 7.5 |
| `test_envelope_mode_respects_capacity` | 512×512 ที่ 0.1 bpnzAC ต้องได้ `EXTERNAL` | 7.5 |
| `test_fingerprint_ignores_coefficients` | แก้ coefficient แล้ว fingerprint ต้องไม่เปลี่ยน | 3.3 |
| `test_ciphertext_from_other_carrier_is_rejected` | AAD ผูกกับ carrier | 8.3 |
| `test_ctr_search_respects_max_skip` | ไฟล์ที่ไม่มีข้อมูลต้องเลิกภายในเพดาน ไม่วนไม่รู้จบ | 7.6 |
| `test_all_fields_are_big_endian` | เทียบกับ vector ที่เขียนด้วยมือ | 7.5 |
| KAT ของ HKDF · GCM-SIV | ตรง reference vector ทุก bit | 7.1 · 7.4 |
