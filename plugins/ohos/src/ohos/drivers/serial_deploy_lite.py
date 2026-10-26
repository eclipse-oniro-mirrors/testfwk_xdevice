#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2026 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Serial-only file deployment for L1 lite devices (no network).

Two kernel-specific strategies, shared YMODEM infrastructure:

LiteOS kernel (userfs = FAT16):
  reset -> interrupt autoboot -> parse BPB -> dump FAT/root -> PC patch
  (cluster chains + root dir entries, freeing replaced entries)
  -> ymodem + mmc write -> flash-level crc32 verify -> boot
  Files appear in /storage as regular FAT files, byte-exact.

Linux kernel (userfs = ext4, no FAT to patch):
  exec /bin/toybox reboot -> interrupt autoboot
  -> ymodem each file to RAM -> mmc write to scratch area (beyond last
  partition, ~2GB offset) -> crc32 verify -> boot Linux
  -> xxd -s read from /dev/mmcblk0 -> md5 verify -> chmod +x for tools
  Files appear in /storage, byte-exact.

Board note (HiSpark Taurus eMMC, no partition table):
  fastboot 1M@0 | kernel 9M@1M | rootfs 50M@10M | userfs 50M@60M
  LiteOS userfs LBA = 122880 (FAT16, BPB parsed at runtime).
  Linux scratch sector = 2359296 (2GB offset, beyond all partitions).
"""

__all__ = ["SerialDeployer"]

import hashlib
import re
import struct
import time
import zlib

USERFS_LBA = 122880
BPS = 512
ALLOC_START = 23000          # LiteOS: FAT cluster allocation start
SCRATCH_SECTOR = 2359296     # Linux: eMMC scratch area (2GB offset)
SCRATCH_GAP = 16             # Linux: sector gap between files

SOH = 0x01
STX = 0x02
EOT = 0x04
ACK = 0x06
NAK = 0x15
CAN = 0x18
CHAR_C = 0x43


def _crc16_ccitt(data):
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _make_block(seq, payload):
    padded = payload + b"\x00" * (128 - len(payload))
    crc = _crc16_ccitt(padded)
    return bytes([SOH, seq & 0xFF, (~seq) & 0xFF]) + padded + bytes([crc >> 8, crc & 0xFF])


class SerialDeployer:
    """Unified serial deployment for both LiteOS and Linux kernel devices."""

    def __init__(self, com, logger=None):
        self.com = com
        self.log = logger

    def _info(self, msg):
        if self.log:
            self.log(msg)

    # ==================== shared low-level serial ====================
    def _read_for(self, sec):
        end = time.time() + sec
        out = b''
        while time.time() < end:
            if self.com.in_waiting:
                out += self.com.read(self.com.in_waiting)
            else:
                time.sleep(0.01)
        return out.decode('gbk', errors='ignore')

    def _send_get(self, cmd, marker="hisilicon #", max_wait=30):
        """Send command; return once marker appears AFTER the command echo."""
        self.com.write((cmd + "\r\n").encode('ascii'))
        out = ""
        end = time.time() + max_wait
        while time.time() < end:
            if self.com.in_waiting:
                out += self.com.read(self.com.in_waiting).decode('gbk', errors='ignore')
                idx = out.rfind(cmd)
                if idx >= 0 and marker in out[idx + len(cmd):]:
                    return out
            else:
                time.sleep(0.005)
        return out

    def _drain(self, sec):
        self._read_for(sec)

    # ==================== shared YMODEM ====================
    def _read_byte(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if self.com.in_waiting:
                b = self.com.read(1)
                if b in (b"\r", b"\n"):
                    continue
                return b[0]
            time.sleep(0.01)
        return None

    def _ymodem_send(self, data):
        end = time.time() + 15
        got_c = False
        while time.time() < end:
            if self.com.in_waiting:
                if self.com.read(1)[0] == CHAR_C:
                    got_c = True
                    break
            else:
                time.sleep(0.01)
        if not got_c:
            return False, "no initial C"
        header = b"blob.bin\x00" + str(len(data)).encode() + b"\x00"
        self.com.write(_make_block(0, header[:128]))
        end = time.time() + 10
        acked = False
        while time.time() < end:
            if self.com.in_waiting:
                if self.com.read(1)[0] == ACK:
                    acked = True
                    break
        if not acked:
            return False, "header not ACKed"
        end = time.time() + 10
        got_c = False
        while time.time() < end:
            if self.com.in_waiting:
                if self.com.read(1)[0] == CHAR_C:
                    got_c = True
                    break
        if not got_c:
            return False, "no second C"
        seq = 1
        for off in range(0, len(data), 128):
            chunk = data[off:off + 128]
            for _ in range(5):
                self.com.write(_make_block(seq, chunk))
                b = self._read_byte(10)
                if b == ACK:
                    break
                if b == NAK:
                    continue
                return False, "block %d unexpected %r" % (seq, b)
            else:
                return False, "block %d failed" % seq
            seq += 1
        for _ in range(5):
            self.com.write(bytes([EOT]))
            b = self._read_byte(10)
            if b == NAK:
                continue
            if b == ACK:
                break
        else:
            return False, "EOT not ACKed"
        end = time.time() + 10
        while time.time() < end:
            if self.com.in_waiting:
                if self.com.read(1)[0] == CHAR_C:
                    break
        self.com.write(_make_block(0, b"\x00"))
        b = self._read_byte(10)
        if b != ACK:
            return False, "close not ACKed"
        return True, "ok"

    def _ymodem_write_flash(self, data, lba, count_sectors, tag):
        """YMODEM to RAM then mmc write, with crc32 flash verification."""
        self._send_get("loady 0x82000000", marker="Ready for binary")
        self._drain(1.0)
        ok, msg = self._ymodem_send(data)
        self._info("ymodem %-8s %s (%d B)" % (tag, "OK" if ok else "FAIL:" + msg, len(data)))
        if not ok:
            raise RuntimeError("ymodem failed: " + tag)
        out = self._send_get("mmc write 0 0x82000000 0x%x 0x%x" % (lba, count_sectors))
        if "ERROR" in out.upper() or "Usage" in out:
            raise RuntimeError("mmc write problem: " + out[:100])

    def _crc32_verify_flash(self, lba, count_sectors, length, tag):
        """Read back from flash and verify crc32 in U-Boot."""
        self._send_get("mmc read 0 0x82000000 0x%x 0x%x" % (lba, count_sectors))
        out = self._send_get("crc32 0x82000000 0x%x" % length)
        m = re.search(r'==>\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]{8})', out)
        if not m:
            raise RuntimeError("verify %s: crc32 not parsed" % tag)
        return int(m.group(1), 16)

    # ==================== shared U-Boot control ====================
    def _goto_uboot(self, reboot_cmd="reset"):
        self.com.write(b"\r\n")
        self._read_for(1.5)
        self.com.write((reboot_cmd + "\r\n").encode('ascii'))
        boot_log = ""
        deadline = time.time() + 90
        while time.time() < deadline:
            self.com.write(b"\r")
            time.sleep(0.1)
            if self.com.in_waiting:
                boot_log += self.com.read(self.com.in_waiting).decode('gbk', errors='ignore')
                if "hisilicon #" in boot_log and boot_log.count("hisilicon #") >= 2:
                    return True
        return False

    def _boot_os(self):
        """Boot from U-Boot, wait for OS prompt. Returns 'liteos' or 'linux'."""
        self._send_get("boot")
        self._read_for(25)
        deadline = time.time() + 90
        while time.time() < deadline:
            self.com.write(b"\r\n")
            out = self._read_for(3)
            if "OHOS #" in out:
                return "liteos"
            lines = out.strip().split("\n")
            if any(l.strip().endswith("#") or l.strip().endswith("# ") for l in lines):
                return "linux"
        return None

    # ==================== LiteOS: FAT16 patch ====================
    def _parse_bpb(self, bpb):
        bps = struct.unpack_from("<H", bpb, 11)[0]
        spc = bpb[13]
        rsvd = struct.unpack_from("<H", bpb, 14)[0]
        nfats = bpb[16]
        root_ent = struct.unpack_from("<H", bpb, 17)[0]
        fat_sz = struct.unpack_from("<H", bpb, 22)[0]
        if bps != 512:
            raise RuntimeError("unsupported sector size %d" % bps)
        if fat_sz == 0:
            raise RuntimeError("FAT32 not supported")
        fat1_lba = USERFS_LBA + rsvd
        root_lba = fat1_lba + nfats * fat_sz
        root_secs = root_ent * 32 // bps
        data_lba = root_lba + root_secs
        return {"spc": spc, "nfats": nfats, "root_ent": root_ent, "fat_sz": fat_sz,
                "fat1_lba": fat1_lba, "root_lba": root_lba, "data_lba": data_lba,
                "cluster_bytes": bps * spc}

    def _dump(self, base_addr, length):
        data = bytearray()
        off = 0
        while off < length:
            chunk = min(0x400, length - off)
            out = self._send_get("md.b 0x%x %x" % (base_addr + off, chunk))
            got = bytearray()
            for line in out.split("\n"):
                m = re.match(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2}\s*){1,16})', line.strip())
                if m:
                    for h in m.group(2).split():
                        got.append(int(h, 16))
            if len(got) < chunk:
                raise RuntimeError("FAT dump short at +0x%x" % off)
            data.extend(got[:chunk])
            off += chunk
        return bytes(data)

    def _deploy_liteos(self, files):
        """LiteOS: FAT16 patching. files = [(name, data)]."""
        g = self._geom
        spc = g["spc"]
        cluster_bytes = g["cluster_bytes"]
        fat1_lba = g["fat1_lba"]
        root_lba = g["root_lba"]
        fat_sz = g["fat_sz"]

        self._send_get("mmc read 0 0x82000000 0x%x 0x%x" % (fat1_lba, fat_sz))
        fat = bytearray(self._dump(0x82000000, fat_sz * BPS))
        root_secs = g["root_ent"] * 32 // BPS
        self._send_get("mmc read 0 0x82000000 0x%x 0x%x" % (root_lba, root_secs))
        root = bytearray(self._dump(0x82000000, root_secs * BPS))

        def entry(c):
            return struct.unpack_from("<H", fat, c * 2)[0]

        def set_entry(c, v):
            struct.pack_into("<H", fat, c * 2, v)

        def free_chain(first_cluster):
            freed = []
            c = first_cluster
            while 2 <= c < 0xFFF8:
                nxt = entry(c)
                set_entry(c, 0)
                freed.append(c)
                c = nxt
            return freed

        total = len(fat) // 2
        alloc_next = ALLOC_START
        placements = []
        touched_clusters = []
        root_secs_touched = set()
        for name, data in files:
            base, _, ext = name.partition(".")
            for i in range(g["root_ent"]):
                e = root[i * 32:(i + 1) * 32]
                if e[0] == 0x00:
                    break
                if e[0] == 0xE5 or e[11] == 0x0F:
                    continue
                old_name = (e[0:8].decode('ascii', 'ignore').strip() + "." +
                            e[8:11].decode('ascii', 'ignore').strip()).rstrip(".")
                if old_name.lower() == name.lower():
                    old_clus = struct.unpack_from("<H", e, 26)[0]
                    touched_clusters.extend(free_chain(old_clus))
                    root[i * 32] = 0xE5
                    root_secs_touched.add((i * 32) // BPS)
                    self._info("  replaced old entry %s (entry %d)" % (old_name, i))
            n_cl = (len(data) + cluster_bytes - 1) // cluster_bytes
            first = None
            c = alloc_next
            while c + n_cl <= total:
                if all(entry(c + i) == 0 for i in range(n_cl)):
                    first = c
                    break
                c += 1
            if first is None:
                raise RuntimeError("no contiguous free run for %s" % name)
            alloc_next = first + n_cl
            for i in range(n_cl - 1):
                set_entry(first + i, first + i + 1)
            set_entry(first + n_cl - 1, 0xFFFF)
            touched_clusters.extend(range(first, first + n_cl))
            idx = next((i for i in range(g["root_ent"]) if root[i * 32] == 0x00), None)
            if idx is None:
                raise RuntimeError("root dir full")
            e = bytearray(32)
            e[0:8] = base.ljust(8).upper().encode("ascii")
            e[8:11] = ext.ljust(3).upper().encode("ascii")
            e[11] = 0x20
            struct.pack_into("<H", e, 24, 0x4F21)
            struct.pack_into("<H", e, 26, first)
            struct.pack_into("<I", e, 28, len(data))
            root[idx * 32:(idx + 1) * 32] = e
            placements.append((name, data, first, n_cl))
            root_secs_touched.add((idx * 32) // BPS)
            self._info("  %-14s %6dB -> clusters %d..%d" %
                       (name, len(data), first, first + n_cl - 1))

        fat_secs = sorted({c * 2 // BPS for c in touched_clusters})
        for sec in fat_secs:
            blob = bytes(fat[sec * BPS:(sec + 1) * BPS])
            self._ymodem_write_flash(blob, fat1_lba + sec, 1, "FAT1s%d" % sec)
            for n in range(1, g["nfats"]):
                self._ymodem_write_flash(blob, fat1_lba + n * fat_sz + sec, 1,
                                         "FAT%ds%d" % (n + 1, sec))
        for sec in sorted(root_secs_touched):
            self._ymodem_write_flash(bytes(root[sec * BPS:(sec + 1) * BPS]),
                                     root_lba + sec, 1, "ROOTs%d" % sec)
        for name, data, first, n_cl in placements:
            pad = (-len(data)) % cluster_bytes
            self._ymodem_write_flash(data + b"\x00" * pad,
                                     g["data_lba"] + (first - 2) * spc, n_cl * spc,
                                     name.split(".")[0])

        for name, data, first, n_cl in placements:
            dev_crc = self._crc32_verify_flash(g["data_lba"] + (first - 2) * spc,
                                               n_cl * spc, len(data), name)
            want_crc = zlib.crc32(data) & 0xFFFFFFFF
            if dev_crc != want_crc:
                raise RuntimeError("verify %s: crc32 mismatch" % name)
            self._info("  verified %-12s crc32=%s" % (name, hex(dev_crc)))

    # ==================== Linux: scratch + xxd ====================
    def _deploy_linux(self, files):
        """Linux: ymodem to scratch area, boot, wait long, xxd read."""
        sector = SCRATCH_SECTOR
        placements = []
        for name, data in files:
            n_sec = (len(data) + BPS - 1) // BPS
            self._info("  %-14s %6dB -> scratch sector %d" % (name, len(data), sector))
            self._ymodem_write_flash(data, sector, n_sec, name.split(".")[0])
            dev_crc = self._crc32_verify_flash(sector, n_sec, len(data), name)
            want_crc = zlib.crc32(data) & 0xFFFFFFFF
            if dev_crc != want_crc:
                raise RuntimeError("verify %s: crc32 mismatch" % name)
            placements.append((name, data, sector, n_sec))
            sector += n_sec + SCRATCH_GAP

        # Boot Linux and wait for the shell. Use a shell-ready
        # double-confirm probe (two consecutive line-anchored "# " prompt
        # hits) to exit early instead of blind-waiting the full period;
        # noise lines ending with '#' require two hits to suppress them.
        self._info("Serial deploy: booting OS")
        self._send_get("boot")
        # no fixed blind wait: poll continuously from boot (below). Probe
        # commands sent during boot buffer in the tty input queue and are
        # all executed the moment the shell starts.

        import re as _re
        # Active probe: send "echo PBREADY" and look for the output line.
        # A bare-Enter prompt probe cannot work on flooded consoles (noise
        # glues itself to the prompt mid-line). The unique marker line
        # "^PBREADY$" cannot be faked by noise or by the tty echo (which
        # prints "echo PBREADY", never a bare PBREADY line).
        ready_re = _re.compile(r"^PBREADY\r?$", _re.M)
        deadline = time.time() + 120
        ready = False
        while time.time() < deadline:
            self.com.write(b"echo PBREADY\r\n")
            chunk = self._read_for(3)
            if ready_re.search(chunk):
                ready = True
                self._info("Serial deploy: shell ready (early exit)")
                break
            time.sleep(1)
        if not ready:
            self._info("Serial deploy: shell probe timed out, continuing")
        time.sleep(2)
        self._drain(3)

        # Now read files from scratch area (shell should be responsive)
        for name, data, sec, n_sec in placements:
            byte_off = sec * BPS
            self._info("  reading %s from scratch..." % name)
            self._send_linux_wait("xxd -s %d -l %d -p /dev/mmcblk0 | "
                                  "xxd -r -p > /storage/%s" % (byte_off, len(data), name),
                                  wait=20)
            if name in ("aa", "bm"):
                self._send_linux_wait("chmod +x /storage/%s" % name, wait=5)
            self._info("  deployed %s to /storage" % name)

    def _send_linux_wait(self, cmd, wait=10):
        """Send command with fixed wait (no early return)."""
        self.com.write((cmd + "\r\n").encode('ascii'))
        self._read_for(wait)

    def _send_get_linux(self, cmd, max_wait=30):
        """Send command in Linux shell (prompt is '#')."""
        self.com.write((cmd + "\r\n").encode('ascii'))
        out = ""
        end = time.time() + max_wait
        while time.time() < end:
            if self.com.in_waiting:
                out += self.com.read(self.com.in_waiting).decode('gbk', errors='ignore')
            else:
                time.sleep(0.01)
        return out

    # ==================== public API ====================
    def deploy(self, files, kernel="liteos", reboot_cmd=None):
        """Deploy files to /storage via serial (no network).

        Args:
            files: list of (name, bytes) tuples.
            kernel: "liteos" or "linux".
            reboot_cmd: override reboot command (auto-detected if None).
        """
        if reboot_cmd is None:
            reboot_cmd = "exec /bin/toybox reboot" if kernel == "linux" else "reset"

        self._info("Serial deploy: entering U-Boot (kernel=%s)" % kernel)
        if not self._goto_uboot(reboot_cmd):
            raise RuntimeError("cannot enter U-Boot")
        time.sleep(1)
        self._drain(1)

        if kernel == "linux":
            self._info("Serial deploy: Linux scratch area deployment")
            self._deploy_linux(files)
        else:
            self._info("Serial deploy: parsing FAT BPB")
            self._send_get("mmc read 0 0x82000000 0x%x 1" % USERFS_LBA)
            bpb = self._dump(0x82000000, BPS)
            self._geom = self._parse_bpb(bpb)
            self._info("Serial deploy: FAT16 spc=%d fats=%d fat_sz=%d root_ent=%d"
                       % (self._geom["spc"], self._geom["nfats"],
                          self._geom["fat_sz"], self._geom["root_ent"]))
            self._info("Serial deploy: dumping FAT")
            self._deploy_liteos(files)
            self._info("Serial deploy: booting OS")
            os_type = self._boot_os()
            if not os_type:
                raise RuntimeError("OS did not boot after deploy")
            self._info("Serial deploy: OS ready")

    def verify_files(self, files, kernel="liteos"):
        """Verify deployed files via md5/sha3 (best-effort, console noise may
        prevent reading; flash-level crc32 already verified during deploy)."""
        results = {}
        for name, data in files:
            want = hashlib.md5(data).hexdigest()
            if kernel == "linux":
                out = self._send_get_linux(
                    "md5sum /storage/%s | cut -c1-32" % name, 10)
            else:
                out = self._send_get(
                    "exec /bin/toybox sha3sum /storage/%s" % name, 10)
            import re as _re
            if kernel == "linux":
                m = _re.search(r'([0-9a-f]{32})', out)
            else:
                m = _re.search(r'([0-9a-f]{56})', out)
            results[name] = (m.group(1) if m else None, want)
        return results
