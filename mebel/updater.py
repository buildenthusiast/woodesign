"""Обновяване от GitHub Releases (github.com/buildenthusiast/woodesign).

При всяка нова версия GitHub Actions качва MebelDesigner.exe в Release с
таг vX.Y.Z. Програмата проверява последния Release и, ако е по-нов, сваля
новия .exe и го подменя след затваряне (чрез малък .bat скрипт).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from . import __version__

REPO = "buildenthusiast/woodesign"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "MebelDesigner.exe"


def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s)[:3]) or (0,)


def _ssl_context():
    import ssl
    try:
        import certifi   # идва с програмата; надежден списък сертификати и в .exe
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa
        return ssl.create_default_context()


def _open(req, timeout, opener=None):
    if opener:
        return opener(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


def log(msg):
    try:
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
        d = os.path.join(base, "MebelDesigner")
        os.makedirs(d, exist_ok=True)
        import datetime
        with open(os.path.join(d, "update.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {__version__}: {msg}\n")
    except Exception:  # noqa
        pass


def _clean_notes(body):
    lines = [ln for ln in (body or "").splitlines()
             if not ln.startswith(("Co-Authored-By:", "Claude-Session:"))]
    return "\n".join(lines).strip()


def _info(tag, url, notes, page):
    if _ver(tag) <= _ver(__version__):
        return None
    return {"version": tag.lstrip("v"), "url": url, "notes": _clean_notes(notes), "page": page}


def check(timeout=10, opener=None):
    """Връща dict(version, url, notes, page) ако има по-нова версия, иначе None.
    Първо GitHub API; при грешка – пренасочването на /releases/latest."""
    hdr = {"Accept": "application/vnd.github+json", "User-Agent": "MebelDesigner-updater"}
    try:
        with _open(urllib.request.Request(API, headers=hdr), timeout, opener) as r:
            rel = json.loads(r.read().decode("utf-8"))
        tag = rel.get("tag_name", "")
        url = next((a["browser_download_url"] for a in rel.get("assets", []) if a.get("name") == ASSET), None)
        return _info(tag, url, rel.get("body", ""), rel.get("html_url", ""))
    except Exception as e:  # noqa
        log(f"API: {e!r} – опит през /releases/latest")
        if opener:
            raise
    page = f"https://github.com/{REPO}/releases/latest"
    with _open(urllib.request.Request(page, headers={"User-Agent": "MebelDesigner-updater"}), timeout) as r:
        final = r.geturl()
    tag = final.rstrip("/").rsplit("/", 1)[-1]
    if not tag.startswith("v"):
        raise IOError("Няма публикувана версия.")
    return _info(tag, f"https://github.com/{REPO}/releases/download/{tag}/{ASSET}", "", final)


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def download_and_replace(url, progress=None):
    """Сваля новия .exe до текущия и пуска скрипт, който го подменя след изход.
    Връща True, ако програмата трябва да се затвори."""
    exe = sys.executable
    new = exe + ".new"
    req = urllib.request.Request(url, headers={"User-Agent": "MebelDesigner-updater"})
    with _open(req, 120) as r, open(new, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    if os.path.getsize(new) < 1_000_000:
        os.remove(new)
        raise IOError("Свалянето е непълно.")
    bat = os.path.join(tempfile.gettempdir(), "mebel_update.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write("@echo off\r\nchcp 65001 >nul\r\n"
                "set n=0\r\n"
                "ping 127.0.0.1 -n 3 >nul\r\n"
                ":retry\r\n"
                f'move /y "{new}" "{exe}" >nul 2>nul && goto ok\r\n'
                "set /a n+=1\r\n"
                "if %n% geq 30 goto ok\r\n"
                "ping 127.0.0.1 -n 2 >nul\r\n"
                "goto retry\r\n"
                ":ok\r\n"
                f'start "" "{exe}"\r\n'
                'del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True
