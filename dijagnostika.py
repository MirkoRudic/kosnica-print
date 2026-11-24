#!/usr/bin/env python3
"""
Izvidjanje Windows stampe. Nista ne menja, samo cita i upisuje u dijagnostika.txt.
Pokrece se preko dijagnostika.bat.
"""
import sys, traceback

def glava(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)

glava("PYTHON")
print(sys.version)
print(sys.executable)

try:
    import win32print, win32con, win32gui, win32ui
    print("pywin32 OK")
except Exception:
    print("pywin32 NIJE DOSTUPAN")
    traceback.print_exc()
    sys.exit(1)

glava("STAMPACI")
try:
    podrazumevani = win32print.GetDefaultPrinter()
except Exception as e:
    podrazumevani = None
    print("GetDefaultPrinter greska:", e)
print("podrazumevani:", podrazumevani)
print()

zastavice = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
imena = []
for p in win32print.EnumPrinters(zastavice, None, 2):
    imena.append(p["pPrinterName"])
    print("  %-40s  drajver: %s  port: %s  status: %s"
          % (p["pPrinterName"], p.get("pDriverName"), p.get("pPortName"), p.get("Status")))

meta = [n for n in imena if "L18050" in n.upper() or "EPSON" in n.upper()]
print("\nkandidati za Epson:", meta if meta else "NEMA")

cilj = meta[0] if meta else podrazumevani
if not cilj:
    print("Nema sta da se ispituje.")
    sys.exit(0)

glava("DEVMODE: %s" % cilj)
try:
    h = win32print.OpenPrinter(cilj)
    try:
        info = win32print.GetPrinter(h, 2)
        dm = info["pDevMode"]
        print("dmDeviceName   ", dm.DeviceName)
        print("dmDriverVersion", dm.DriverVersion)
        print("dmSize         ", dm.Size)
        print("dmDriverExtra  ", dm.DriverExtra, " <- Epsonov privatni blok")
        print("dmFields       ", hex(dm.Fields))
        for polje in ("Orientation", "PaperSize", "PaperLength", "PaperWidth",
                      "Scale", "Copies", "DefaultSource", "PrintQuality",
                      "Color", "Duplex", "YResolution", "TTOption", "Collate",
                      "MediaType", "DitherType"):
            try:
                print("  %-14s %s" % (polje, getattr(dm, polje)))
            except Exception:
                pass
    finally:
        win32print.ClosePrinter(h)
except Exception:
    traceback.print_exc()

glava("FORMATI PAPIRA I REZOLUCIJE")
try:
    h = win32print.OpenPrinter(cilj)
    port = win32print.GetPrinter(h, 2)["pPortName"]
    win32print.ClosePrinter(h)
    imena_p = win32print.DeviceCapabilities(cilj, port, win32con.DC_PAPERNAMES)
    brojevi = win32print.DeviceCapabilities(cilj, port, win32con.DC_PAPERS)
    velicine = win32print.DeviceCapabilities(cilj, port, win32con.DC_PAPERSIZE)
    print("papira:", len(imena_p))
    for ime, br, vel in list(zip(imena_p, brojevi, velicine)):
        if any(k in ime.upper() for k in ("A4", "A3", "LETTER", "10X15", "CUSTOM", "USER")):
            print("  %-30s id=%-5s %s x %s (0.1 mm)" % (ime.strip("\x00"), br, vel[0], vel[1]))
    try:
        rez = win32print.DeviceCapabilities(cilj, port, win32con.DC_ENUMRESOLUTIONS)
        print("rezolucije:", rez)
    except Exception as e:
        print("rezolucije: nedostupno", e)
except Exception:
    traceback.print_exc()

glava("MERE UREDJAJA (preko DC)")
try:
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(cilj)
    LOGPIXELSX, LOGPIXELSY = 88, 90
    HORZSIZE, VERTSIZE = 4, 6
    HORZRES, VERTRES = 8, 10
    PHYSICALWIDTH, PHYSICALHEIGHT = 110, 111
    PHYSICALOFFSETX, PHYSICALOFFSETY = 112, 113
    for ime, i in (("dpi X", LOGPIXELSX), ("dpi Y", LOGPIXELSY),
                   ("sirina mm", HORZSIZE), ("visina mm", VERTSIZE),
                   ("stampajuca sirina px", HORZRES), ("stampajuca visina px", VERTRES),
                   ("fizicka sirina px", PHYSICALWIDTH), ("fizicka visina px", PHYSICALHEIGHT),
                   ("odmak X px", PHYSICALOFFSETX), ("odmak Y px", PHYSICALOFFSETY)):
        print("  %-24s %s" % (ime, dc.GetDeviceCaps(i)))
    dc.DeleteDC()
except Exception:
    traceback.print_exc()

glava("KRAJ")
