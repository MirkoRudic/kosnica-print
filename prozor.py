"""Prozor aplikacije (PRAVILA.md P3, P4): Edge --app sa sopstvenim profilom, ikonica pored sata
(Otvori / Ugasi), a gašenje zatvara i prozor."""
import os
import shutil
import subprocess
import threading
import webbrowser

OVDE = os.path.dirname(os.path.abspath(__file__))
NASLOV = "Košnica Print"


def _prozori():
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    nadjeni = []

    def cb(h, _):
        n = u.GetWindowTextLengthW(h)
        if n and u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(n + 1)
            u.GetWindowTextW(h, b, n + 1)
            k = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(h, k, 64)
            if b.value.startswith(NASLOV) and k.value.startswith("Chrome_WidgetWin"):
                nadjeni.append(h)
        return True
    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return nadjeni


def otvori(url):
    """Postojeći prozor ide u prvi plan; inače novi Edge --app prozor."""
    try:
        h = _prozori()
        if h:
            import ctypes
            u = ctypes.windll.user32
            if u.IsIconic(h[0]):
                u.ShowWindow(h[0], 9)
            u.SetForegroundWindow(h[0])
            return
    except Exception:
        pass
    for exe in [shutil.which("msedge"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
        if exe and os.path.exists(exe):
            subprocess.Popen([exe, "--app=" + url, "--user-data-dir=" + os.path.join(OVDE, "podaci", "edge"),
                              "--no-first-run", "--no-default-browser-check", "--disable-sync",
                              "--start-maximized"])
            return
    webbrowser.open(url)


def zatvori():
    """P4: posle gašenja zatvara se i prozor (WM_CLOSE)."""
    try:
        import ctypes
        for h in _prozori():
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)
    except Exception:
        pass


def ikonica(url, ugasi):
    """Ikonica pored sata u svojoj niti; bez pystray samo se preskače."""
    def radi():
        try:
            import pystray
            from PIL import Image
            slika = Image.open(os.path.join(OVDE, "kosnica.ico"))
            pystray.Icon("kosnica-print", slika, NASLOV, pystray.Menu(
                pystray.MenuItem("Otvori", lambda: otvori(url), default=True),
                pystray.MenuItem("Ugasi", lambda: ugasi()))).run()
        except Exception:
            pass
    threading.Thread(target=radi, name="ikonica", daemon=True).start()
