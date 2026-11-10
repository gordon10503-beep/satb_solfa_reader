"""Loopback-only server. Scores, scans and undo history stay in local SQLite."""
from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
import webbrowser
import errno
import gzip
import io
import zipfile
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .document import (MAX_BYTES, append_bar, edit_symbol, move_part, rename_part, edit_note, edit_meter, engrave, inspect,
                       new_score, read_xml, replace_bar, xml_bytes)

from PIL import Image
from .scan_preprocess import prepare_for_omr
from .pdf_meter import recover_opening_meter
from .recognition_profile import recognition_flags
from .scan_options import selected_pages, repair_satb_book

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"


def scan_status(server, job):
    """Stage progress is real; recognition itself has no reliable percentage."""
    result = dict(server.jobs.get(job, {"status": "error", "error": "Job not found."}))
    if "started" in result:
        result["elapsed"] = max(0, int(result.get("finished", time.time()) - result["started"]))
    if result.get("status") == "running" and result.get("stage") == 1:
        log = server.library.path.parent / "scans" / job / "recognition.log"
        try:
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 12000))
                entries = re.findall(r"StepMonitoring[^\n]*\|\s*([A-Z_]+)", stream.read().decode("utf-8", errors="replace"))
            if entries:
                result["detail"] = "Recognizing: " + entries[-1].lower().replace("_", " ")
        except OSError:
            pass
    return result


def audiveris_path():
    configured = os.environ.get("AUDIVERIS_CMD")
    if configured:
        return shutil.which(configured) or (configured if Path(configured).is_file() else None)
    return shutil.which("audiveris") or next((str(p) for p in [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Audiveris/Audiveris.exe"
    ] if p.is_file()), None)


class Library:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS scores (
                    id TEXT PRIMARY KEY, xml BLOB NOT NULL, meta TEXT NOT NULL,
                    source BLOB, source_type TEXT, updated REAL NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, score TEXT, xml BLOB, meta TEXT);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def list(self):
        with self.connect() as db:
            return [{"id": r["id"], **json.loads(r["meta"]), "updated": r["updated"], "revision": r["revision"]}
                    for r in db.execute("SELECT id,meta,updated,revision FROM scores ORDER BY updated DESC")]

    def get(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM scores WHERE id=?", (sid,)).fetchone()
            if row is None: raise ValueError("Score not found.")
            result = dict(row)
            result["meta"] = json.loads(result["meta"])
            return result

    def add(self, data, meta=None, source=None, source_type=None):
        root = read_xml(data)
        info = inspect(root)
        sid = uuid.uuid4().hex
        meta = {"title": info["title"], "composer": info["composer"], "group": "Ungrouped",
                "bookmarks": [], "reviewed": False, "origin": "MusicXML", **(meta or {})}
        with self.connect() as db:
            db.execute("INSERT INTO scores VALUES (?,?,?,?,?,?,1)",
                       (sid, xml_bytes(root), json.dumps(meta), source, source_type, time.time()))
        return sid

    def update(self, sid, revision, data=None, metadata=None, undo=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM scores WHERE id=?", (sid,)).fetchone()
            if row is None: raise ValueError("Score not found.")
            if row["revision"] != revision:
                raise ValueError("This score changed in another window. Reopen it before editing.")
            meta = json.loads(row["meta"])
            if undo:
                old = db.execute("SELECT * FROM history WHERE score=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
                if old is None: raise ValueError("There are no earlier changes to undo.")
                data, meta = old["xml"], json.loads(old["meta"])
                db.execute("DELETE FROM history WHERE id=?", (old["id"],))
            else:
                db.execute("INSERT INTO history(score,xml,meta) VALUES (?,?,?)", (sid, row["xml"], row["meta"]))
                if metadata is not None:
                    for field in ("group", "bookmarks", "reviewed", "mixer", "practice", "annotations", "playbackReady", "scanError", "title", "trashed"):
                        if field in metadata: meta[field] = metadata[field]
                if data is not None:
                    info = inspect(read_xml(data))
                    meta.update(title=meta.get("title", info["title"]), composer=info["composer"], reviewed=False)
                # Keep a bounded, persistent undo history per score.
                db.execute("DELETE FROM history WHERE score=? AND id NOT IN (SELECT id FROM history WHERE score=? ORDER BY id DESC LIMIT 50)", (sid, sid))
            db.execute("UPDATE scores SET xml=?,meta=?,updated=?,revision=revision+1 WHERE id=?",
                       (data if data is not None else row["xml"], json.dumps(meta), time.time(), sid))
        return self.get(sid)


@functools.lru_cache(maxsize=6)
def rendered(data, mode, minor_do, solfa):
    return engrave(data, mode, minor_do, solfa)


def seed(library):
    if library.list(): return
    data = new_score("Morning light", "A practice sketch · Solfa Studio", bars=8)
    phrases = [
        ["C5/q D5/q E5/q G5/q", "A5/h G5/h", "F5/q E5/q D5/h", "E5/w", "G5/q A5/q G5/q E5/q", "F5/h D5/h", "E5/q D5/q C5/q B4/q", "C5/w"],
        ["G4/h C5/h", "C5/w", "A4/h B4/h", "C5/w", "C5/h B4/h", "A4/h B4/h", "G4/h G4/h", "G4/w"],
        ["E4/w", "E4/h D4/h", "F4/h G4/h", "G4/w", "E4/h G4/h", "F4/w", "E4/h D4/h", "E4/w"],
        ["C3/w", "A2/h E3/h", "F3/h G3/h", "C3/w", "C3/h E3/h", "D3/h G2/h", "C3/h G2/h", "C3/w"]]
    for pi, bars in enumerate(phrases):
        for mi, phrase in enumerate(bars): data = replace_bar(data, pi, mi, phrase)
    library.add(data, {"group": "Practice room", "origin": "Demo", "reviewed": True,
                       "bookmarks": [{"measure": 4, "label": "Second phrase"}]})


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    # Windows permits two listeners with SO_REUSEADDR; never shadow another app.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, library):
        super().__init__(address, Handler)
        self.library, self.token, self.jobs = library, secrets.token_urlsafe(32), {}


class Handler(BaseHTTPRequestHandler):
    server_version = "SolfaStudio/1.0"

    def log_message(self, *_):
        pass

    def respond(self, data, kind="application/json", status=200, etag=None):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode() if kind == "application/json" else data.encode()
        if etag and self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "private, max-age=0, must-revalidate")
            self.end_headers()
            return
        compressed = len(data) > 4096 and "gzip" in self.headers.get("Accept-Encoding", "") and (
            "json" in kind or kind.startswith("text/") or "javascript" in kind)
        if compressed:
            data = gzip.compress(data, compresslevel=3)
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, max-age=0, must-revalidate" if etag else "no-store")
        if etag: self.send_header("ETag", etag)
        self.send_header("Vary", "Accept-Encoding")
        if compressed: self.send_header("Content-Encoding", "gzip")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data:; media-src 'self' blob:; object-src 'self'; frame-src 'self'; connect-src 'self'; frame-ancestors 'self'")
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return self.headers.get("Host") in allowed and (
            not self.headers.get("Origin") or self.headers["Origin"] in {f"http://{h}" for h in allowed})

    def do_GET(self):
        if not self.allowed(): return self.respond({"error": "Local access only."}, status=403)
        path = urlparse(self.path)
        try:
            if path.path == "/api/library":
                return self.respond({"scores": self.server.library.list(), "scanner": bool(audiveris_path()),
                                     "storage": str(self.server.library.path), "build": "2026-11-11-lyrics",
                                     "scanJobs": [{"job": job, **scan_status(self.server, job)} for job in list(self.server.jobs)]})
            if path.path.startswith("/api/job/"):
                return self.respond(scan_status(self.server, path.path.split("/")[-1]))
            if path.path.startswith("/api/score/"):
                row = self.server.library.get(path.path.split("/")[-1])
                q = parse_qs(path.query)
                mode = q.get("mode", ["movable"])[0]
                if mode not in ("movable", "fixed", "pitch"): raise ValueError("Invalid sol-fa mode.")
                result = rendered(row["xml"], mode, q.get("minor", ["false"])[0] == "true", q.get("solfa", ["true"])[0] == "true")
                return self.respond({**result, "id": row["id"], "meta": row["meta"], "revision": row["revision"], "hasSource": row["source"] is not None, "sourceType": row["source_type"], "title": row["meta"].get("title", result["title"])})
            if path.path.startswith("/api/bundle/"):
                row = self.server.library.get(path.path.split("/")[-1])
                title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", row["meta"]["title"]).strip(" .")[:120] or "Score"
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
                    bundle.writestr(f"{title}/{title}.musicxml", row["xml"])
                    if row["source"] is not None:
                        extension = mimetypes.guess_extension(row["source_type"] or "") or ".bin"
                        bundle.writestr(f"{title}/Original{extension}", row["source"])
                return self.respond(archive.getvalue(), "application/zip")
            if path.path.startswith("/api/xml/"):
                row = self.server.library.get(path.path.split("/")[-1])
                return self.respond(row["xml"], "application/vnd.recordare.musicxml+xml")
            if path.path.startswith("/api/source/"):
                row = self.server.library.get(path.path.split("/")[-1])
                if row["source"] is None: raise ValueError("No source scan is attached.")
                return self.respond(row["source"], row["source_type"])
            if path.path == "/api/session": return self.respond({"token": self.server.token})
            relative = "index.html" if path.path == "/" else path.path.lstrip("/")
            file = (STATIC / relative).resolve()
            if not file.is_relative_to(STATIC.resolve()) or not file.is_file():
                return self.respond({"error": "Not found"}, status=404)
            kind = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html"}.get(file.suffix, mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            stat = file.stat()
            return self.respond(file.read_bytes(), kind, etag=f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"')
        except (ValueError, KeyError, IndexError, RuntimeError, OSError) as exc:
            self.respond({"error": str(exc)}, status=400)
        except Exception:
            import traceback
            traceback.print_exc()
            self.respond({"error": "Could not process this score. Check its MusicXML structure."}, status=422)

    def do_POST(self):
        if not self.allowed() or self.headers.get("X-Studio-Token") != self.server.token:
            return self.respond({"error": "Reload the local app to continue."}, status=403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BYTES * 1.4: raise ValueError("Request is empty or too large (40 MB file limit).")
            payload = json.loads(self.rfile.read(length))
            route = urlparse(self.path).path
            lib = self.server.library
            if route == "/api/new":
                return self.respond({"id": lib.add(new_score(**payload), {"origin": "Composition"})})
            if route == "/api/import-pair":
                pdf = base64.b64decode(payload["pdf"], validate=True)
                notation = base64.b64decode(payload["data"], validate=True)
                if not pdf.startswith(b"%PDF-") or len(pdf)+len(notation)>MAX_BYTES:
                    raise ValueError("Choose a PDF and matching MusicXML under 40 MB combined.")
                name = payload["name"]
                meta = {"title": name, "sourceFileName": name, "origin": "Paired MusicXML", "playbackReady": True}
                return self.respond({"id": lib.add(notation, meta, pdf, "application/pdf")})
            if route == "/api/import":
                data = base64.b64decode(payload["data"], validate=True)
                return self.respond({"id": lib.add(data, {"title": payload["name"], "sourceFileName": payload["name"]})})
            if route in ("/api/scan", "/api/rescan"):
                options = payload.get("options", {})
                pages = selected_pages(options.get("pages"))
                language = options.get("language", "default")
                if language not in ("default","eng","chi_tra+eng","chi_sim+eng"): raise ValueError("Unsupported text language.")
                cue_mode = options.get("cueNotes", "auto")
                if cue_mode not in ("auto", "on", "off"): raise ValueError("Unknown cue-note setting.")
                layout = options.get("layout", "auto")
                if layout not in ("auto", "satb-piano", "satb", "piano"): raise ValueError("Unknown ensemble preset.")
                rescan_row = lib.get(payload["id"]) if route == "/api/rescan" else None
                if rescan_row:
                    if rescan_row["source"] is None: raise ValueError("No original scan is attached.")
                    if any(j.get("id") == payload["id"] and j.get("status") == "running" for j in self.server.jobs.values()): raise ValueError("This score is already scanning.")
                    payload["name"] = rescan_row["meta"].get("sourceFileName", rescan_row["meta"]["title"])
                command = audiveris_path()
                data = rescan_row["source"] if rescan_row else base64.b64decode(payload["data"], validate=True)
                ext = Path(payload["name"]).suffix.lower()
                if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff") or len(data) > MAX_BYTES:
                    raise ValueError("Choose a PDF, PNG, JPEG or TIFF under 40 MB.")
                sid = payload["id"] if rescan_row else lib.add(new_score(title=Path(payload["name"]).stem, template="melody", bars=1), {"origin": "Scan", "playbackReady": False, "title": payload["name"], "sourceFileName": payload["name"]}, data, "application/pdf" if ext == ".pdf" else mimetypes.guess_type(payload["name"])[0])
                if not command: return self.respond({"id": sid, "job": None})
                job = uuid.uuid4().hex
                self.server.jobs[job] = {"status": "running", "stage": 0, "started": time.time(), "id": sid,
                                         "name": payload["name"], "message": "Preparing scan"}
                threading.Thread(target=scan, args=(self.server, job, command, data, ext, sid, {"pages": pages, "layout": layout, "cueNotes": cue_mode, "language": language}), daemon=True).start()
                return self.respond({"job": job, "id": sid})
            sid, revision = payload["id"], int(payload["revision"])
            row = lib.get(sid)
            if route == "/api/duplicate":
                meta = dict(row["meta"])
                meta.update(title=meta["title"] + " (copy)", trashed=False)
                return self.respond({"id": lib.add(row["xml"], meta, row["source"], row["source_type"])})
            if route == "/api/meta":
                result = lib.update(sid, revision, metadata=payload["meta"])
            elif route == "/api/undo": result = lib.update(sid, revision, undo=True)
            elif route == "/api/edit":
                action = payload["action"]
                metadata = None
                if action == "note": data = edit_note(row["xml"], **payload["values"])
                elif action == "symbol": data = edit_symbol(row["xml"], **payload["values"])
                elif action == "move-part":
                    values = payload["values"]
                    data = move_part(row["xml"], **values)
                    first = values["part"]
                    second = first + values["direction"]
                    mixer = list(row["meta"].get("mixer") or [])
                    if mixer:
                        while len(mixer) <= max(first, second):
                            mixer.append({})
                        mixer[first], mixer[second] = mixer[second], mixer[first]
                        metadata = {"mixer": mixer}
                elif action == "rename-part": data = rename_part(row["xml"], **payload["values"])
                elif action == "bar": data = replace_bar(row["xml"], **payload["values"])
                elif action == "append": data = append_bar(row["xml"])
                elif action == "meter": data = edit_meter(row["xml"], **payload["values"])
                elif action == "xml": data = xml_bytes(read_xml(payload["xml"].encode()))
                else: raise ValueError("Unknown edit action.")
                # Validate engraving before making the new document durable.
                rendered(data, "movable", False, True)
                result = lib.update(sid, revision, data=data, metadata=metadata)
            else: raise ValueError("Unknown operation.")
            self.respond({"id": sid, "revision": result["revision"], "meta": result["meta"]})
        except Exception as exc:
            self.respond({"error": str(exc) or "Could not save the score."}, status=400)


def scan(server, job, command, data, ext, sid=None, options=None):
    options = options or {}
    sheet_args = ["-sheets", *options["pages"]] if options.get("pages") else []
    server.jobs.setdefault(job, {"status": "running", "stage": 0, "started": time.time(), "id": sid, "name": "Score scan"})
    def progress(stage, message, **extra):
        server.jobs[job] = {**server.jobs[job], "stage": stage, "message": message, **extra}
    folder = server.library.path.parent / "scans" / job
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / f"scan{ext}"
    source.write_bytes(data)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        with (folder / "recognition.log").open("w", encoding="utf-8") as log:
            progress(1, "Checking page orientation and staff alignment")
            try:
                recognition_source = prepare_for_omr(source, options.get("pages") or ())
            except (OSError, ValueError, RuntimeError, Image.DecompressionBombError) as exc:
                print(f"Page preparation unavailable; continuing with original: {exc}", file=log)
                recognition_source = source
            progress(1, "Recognizing music · large scores can take several minutes")
            flags_for_book = recognition_flags(options.get("cueNotes", "auto"), data, ext, options.get("pages"))
            language = options.get("language","default")
            if language != "default":
                flags_for_book.extend(["-constant", "org.audiveris.omr.text.Language.defaultSpecification=" + language])
            print("Recognition settings:", flags_for_book or "engine default", file=log, flush=True)
            subprocess.run([command, "-batch", "-step", "PAGE", "-save", *flags_for_book, "-output", str(folder), *sheet_args, "--", str(recognition_source)],
                           stdout=log, stderr=subprocess.STDOUT, timeout=1200, check=True, **flags)
            books = list(folder.rglob("*.omr"))
            if not books: raise ValueError("Audiveris did not produce a score book. Inspect the recognition log.")
            if options.get("layout", "auto") != "auto": repair_satb_book(books[0], options["layout"])
            exported = []
            progress(2, "Exporting recognized notation")
            for _ in range(2):
                subprocess.run([command, "-batch", "-export", *flags_for_book, *sheet_args, "--", str(books[0])],
                               stdout=log, stderr=subprocess.STDOUT, timeout=1200, check=False, **flags)
                exported = list(folder.rglob("*.mxl")) + list(folder.rglob("*.musicxml"))
                if exported: break
            if not exported: raise ValueError("Recognition produced no MusicXML. Review the book in Audiveris.")
        progress(3, "Checking and saving the result")
        output = exported[0].read_bytes()
        meter = None
        if ext == ".pdf":
            pages = options.get("pages") or [1]
            output, meter = recover_opening_meter(output, data, int(pages[0]))
        if meter:
            server.jobs[job]["meterEvidence"] = f"Opening {meter[0]}/{meter[1]} recovered from matching printed meter symbols."
        # A readable export is still unverified; keep its source for comparison.
        inspect(read_xml(output))
        if sid is None:
            sid = server.library.add(output, {"origin": "Scan", "reviewed": False, "playbackReady": True}, data,
                                     "application/pdf" if ext == ".pdf" else mimetypes.guess_type(source.name)[0])
        else:
            # Scan completion must not overwrite concurrent annotation edits.
            with server.library.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT meta FROM scores WHERE id=?", (sid,)).fetchone()
                meta = json.loads(row["meta"]);meta.update(playbackReady=True, reviewed=False)
                db.execute("UPDATE scores SET xml=?,meta=?,revision=revision+1 WHERE id=?", (xml_bytes(read_xml(output)),json.dumps(meta),sid))
        progress(4, "Scan ready · check the result against the original", status="done", id=sid, finished=time.time())
    except Exception as exc:
        progress(server.jobs[job].get("stage", 0), "Scanning failed · your original is still available", status="error",
                 finished=time.time(), error=f"{exc} Log: {folder / 'recognition.log'}")


def start_or_reuse(port, library, open_browser=True):
    """Reuse only a verified Studio serving this same library."""
    url = f"http://127.0.0.1:{port}"
    try:
        return StudioServer(("127.0.0.1", port), library)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
            raise
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url + "/api/library", timeout=2) as response:
                is_studio = response.headers.get("Server", "").startswith("SolfaStudio/")
                info = json.load(response)
            same_library = Path(info.get("storage", "")).resolve() == library.path.resolve()
            if is_studio and same_library and info.get("build") != "2026-11-11-lyrics":
                print("An older Studio is running; opening the updated version on the next port.", flush=True)
                return start_or_reuse(port + 1, library, open_browser)
            if is_studio and same_library:
                print(f"Solfa Studio is already running: {url}\nOpening the existing workspace.", flush=True)
                if open_browser:
                    webbrowser.open(url)
                return None
        except (OSError, ValueError, TypeError):
            pass
        raise RuntimeError(
            f"Port {port} is already in use by another app or a different Studio library. "
            f"Start Studio with --port {port + 1}, or close the app using that port."
        ) from None


def main():
    parser = argparse.ArgumentParser(description="Solfa Studio — local music workspace")
    parser.add_argument("--port", type=int, default=8873)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    lib = Library(args.data_dir / "library.sqlite3")
    seed(lib)
    try:
        server = start_or_reuse(args.port, lib, open_browser=not args.no_browser)
    except (RuntimeError, OSError) as exc:
        parser.exit(1, f"Could not start Studio: {exc}\n")
    if server is None:
        return
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Solfa Studio: {url}\nLibrary: {lib.path}\nPress Ctrl+C to stop.", flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
