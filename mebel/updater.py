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


def check(timeout=8, opener=None):
    """Връща dict(version, url, notes, page) ако има по-нова версия, иначе None."""
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json", "User-Agent": "MebelDesigner-updater"})
    with opener(req, timeout=timeout) as r:
        rel = json.loads(r.read().decode("utf-8"))
    tag = rel.get("tag_name", "")
    if _ver(tag) <= _ver(__version__):
        return None
    url = next((a["browser_download_url"] for a in rel.get("assets", []) if a.get("name") == ASSET), None)
    return {"version": tag.lstrip("v"), "url": url, "notes": rel.get("body", "") or "", "page": rel.get("html_url", "")}


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def download_and_replace(url, progress=None):
    """Сваля новия .exe до текущия и пуска скрипт, който го подменя след изход.
    Връща True, ако програмата трябва да се затвори."""
    exe = sys.executable
    new = exe + ".new"
    req = urllib.request.Request(url, headers={"User-Agent": "MebelDesigner-updater"})
    with urllib.request.urlopen(req, timeout=60) as r, open(new, "wb") as f:
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
