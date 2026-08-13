# Security Policy

## ขอบเขตที่ระบบนี้ป้องกัน

ดูรายละเอียดเต็มใน `docs/PROJECT_STRUCTURE.md` 2.6 (threat model)

**ป้องกัน:** passive/active warden · network MITM · harvest-now-decrypt-later ·
malicious file ที่ป้อนเข้า analyzer

**ไม่ป้องกัน:** endpoint compromise เต็มรูป · coercion · memory compromise ของ
Python process · robustness ต่อการบีบอัดซ้ำ · deniability

## สิ่งที่ระบบนี้ไม่เคลม

- **ไม่มี post-compromise security** ใน Phase 1 - มีแค่ forward secrecy
  ภายใต้สมมติฐานว่า chain key เก่าถูกลบสำเร็จ
- **ไม่รับประกันว่าตรวจจับไม่ได้** - รายงานเป็น P_E ต่อ detector ที่ระบุชื่อเท่านั้น
- **ไม่รับประกันการล้าง memory** - Python ทำได้ไม่สมบูรณ์ ประกาศเป็นข้อจำกัดที่รู้ตัว

## Known gaps

| Gap | แผน |
|---|---|
| Post-compromise security | Phase 2 (re-KEM) |
| Rollback โดยผู้โจมตีที่ตั้งใจ | Phase 2 (TPM / OS counter) |
| C-level memory bug ใน libjpeg | ชดเชยด้วย sandbox · Phase 2 ใช้ libFuzzer |
| PQ sender authentication แบบไม่มี signature | ข้อจำกัดของ ML-KEM เอง |

## รายงานช่องโหว่

TODO: ใส่ช่องทางติดต่อและนโยบายเปิดเผยก่อน release
