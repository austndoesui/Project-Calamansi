"""Stage31 requires a bounded temporary framebuffer and real XNU exception."""
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from test_stage24_usb import fake_capture

HERE=Path(__file__).resolve().parent


def capture(*, height=640, omit=None, no_fault=False, reorder=False):
    source=fake_capture()
    packets=[]
    for off in range(0,len(source),56):
        pkt=bytearray(source[off:off+56])
        ev=struct.unpack_from('<I',pkt,16)[0]
        if no_fault and ev in (0x2206,0x2400,0x2401,0x2402,0x2403,
                              0x2404,0x2405,0x2406,0x2407,0x241f,
                              0x2207,0x2208,0x2209,0x220a,0x20b3,
                              0x20a3,0x220b,0x2308,0x20ff,0x19ff):
            continue
        if ev==0x2407:
            struct.pack_into('<Q',pkt,44,31)
        packets.append((ev,pkt))
        if ev==0x2302:
            for extra,values in (
                (0x2600,(1440,height,2880)),
                (0x2601,(0x5e605000,0xfffffff049dbb000,0xfffffff04a000000))):
                if extra==omit:
                    continue
                ep=bytearray(pkt)
                struct.pack_into('<I',ep,16,extra)
                struct.pack_into('<QQQ',ep,28,*values)
                packets.append((extra,ep))
    if reorder:
        positions=[i for i,(ev,_) in enumerate(packets) if ev in (0x2600,0x2601)]
        packets[positions[0]],packets[positions[1]]=packets[positions[1]],packets[positions[0]]
    raw=bytearray()
    for i,(_,pkt) in enumerate(packets):
        pkt[6]=31
        struct.pack_into('<I',pkt,8,i)
        struct.pack_into('<Q',pkt,20,13*i)
        struct.pack_into('<I',pkt,52,zlib.crc32(pkt[:52]))
        raw.extend(pkt)
    return bytes(raw)


class Stage26USB(unittest.TestCase):
    def test_stage31_bridge_and_register_provenance(self):
        with tempfile.TemporaryDirectory(dir=HERE/'out/cactus') as folder:
            path=Path(folder)/'capture.bin'
            cmd=[sys.executable,str(HERE/'decode-cactus-usb.py'),
                 str(path),'--require-stage26','--show','0']

            def check(data):
                path.write_bytes(data)
                return subprocess.run(cmd,capture_output=True,text=True)

            good=check(capture())
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            self.assertIn('STAGE26 GENUINE XNU FAULT CAPTURED',good.stdout)

            partial=check(capture(no_fault=True))
            self.assertEqual(partial.returncode,2,partial.stdout+partial.stderr)

            for bad in (capture(height=1440),capture(height=0),
                        capture(omit=0x2600),capture(omit=0x2601),
                        capture(reorder=True),capture()[:-56]):
                res=check(bad)
                self.assertNotEqual(res.returncode,0,res.stdout)


if __name__=='__main__':
    unittest.main()
