import asyncio
import os
import subprocess
from typing import Optional, Dict, Any, List

import aiohttp

from .. import console

API_URL = getattr(console, "SHRUTI_API_URL", None) or "https://aruyt.up.railway.app"
API_KEY = getattr(console, "SHRUTI_API_KEY", None) or "YUKI-XJd3KfUSWeuOWsiZyuIrlmQf"
DOWNLOAD_DIR = "downloads"

_dl_locks: Dict[str, asyncio.Lock] = {}


def _get_lock(key: str) -> asyncio.Lock:
    lock = _dl_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _dl_locks[key] = lock
    return lock


def check_duration(file_path: str) -> float:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return float(out.strip())
    except Exception:
        return 0.0


def has_video_stream(file_path: str) -> bool:
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                file_path,
            ],
            stderr=subprocess.DEVNULL,
            timeout=12,
        )
        return b"video" in out.lower()
    except Exception:
        return False


def _to_vidid(value: str) -> str:
    value = str(value or "").strip()
    if "v=" in value:
        value = value.split("v=")[-1].split("&")[0]
    if "youtu.be/" in value:
        value = value.split("youtu.be/")[-1].split("?")[0]
    return value.strip()


def _safe_str(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _parse_thumb(r: dict) -> str:
    thumbs = r.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        first = thumbs[0] if isinstance(thumbs[0], dict) else {}
        url = first.get("url")
        if url:
            return _safe_str(url).split("?")[0]
    for key in ("thumbnail", "thumb", "image"):
        val = r.get(key)
        if isinstance(val, str) and val:
            return val.split("?")[0]
        if isinstance(val, dict) and val.get("url"):
            return _safe_str(val.get("url")).split("?")[0]
    vidid = _safe_str(r.get("id") or r.get("vidid"))
    if vidid:
        return f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg"
    return ""


def _parse_channel(r: dict) -> str:
    ch = r.get("channel")
    if isinstance(ch, dict):
        return _safe_str(ch.get("name") or ch.get("title"), "YouTube Music")
    if isinstance(ch, str) and ch.strip():
        return ch.strip()
    for key in ("channelName", "uploader", "artist"):
        val = r.get(key)
        if val:
            return _safe_str(val, "YouTube Music")
    return "YouTube Music"


def _normalize_result(r: dict) -> Optional[Dict[str, Any]]:
    if not isinstance(r, dict):
        return None

    vidid = _safe_str(r.get("id") or r.get("vidid") or r.get("video_id"))
    if not vidid and r.get("link"):
        vidid = _to_vidid(_safe_str(r.get("link")))
    if not vidid and r.get("url"):
        vidid = _to_vidid(_safe_str(r.get("url")))
    if not vidid or len(vidid) < 5:
        return None

    title = _safe_str(r.get("title"), "Unknown")
    duration = _safe_str(
        r.get("duration") or r.get("duration_min") or r.get("duration_string"), "0:00"
    )
    if isinstance(r.get("duration"), (int, float)) and r.get("duration"):
        secs = int(r["duration"])
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        duration = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    link = _safe_str(r.get("link") or r.get("url")) or f"https://www.youtube.com/watch?v={vidid}"

    return {
        "title": title,
        "link": link,
        "vidid": vidid,
        "duration_min": duration,
        "thumbnail": _parse_thumb({**r, "id": vidid}),
        "channel": _parse_channel(r),
    }


async def _search_yts(query: str) -> Optional[Dict[str, Any]]:
    try:
        from youtubesearchpython.__future__ import VideosSearch

        results = VideosSearch(str(query).strip(), limit=5)
        data = await results.next()
        items = data.get("result") or []
        for item in items:
            parsed = _normalize_result(item)
            if parsed:
                return parsed
    except Exception as e:
        print(f"[Youtube.search yts] {e}", flush=True)
    return None


async def _search_ytdlp(query: str) -> Optional[Dict[str, Any]]:
    try:
        import yt_dlp

        def _run():
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "default_search": "ytsearch",
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                return info

        info = await asyncio.to_thread(_run)
        entries = (info or {}).get("entries") or []
        for entry in entries:
            if not entry:
                continue
            parsed = _normalize_result(
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "duration": entry.get("duration"),
                    "url": entry.get("url") or entry.get("webpage_url"),
                    "link": entry.get("webpage_url") or entry.get("url"),
                    "channel": entry.get("channel") or entry.get("uploader"),
                    "thumbnails": entry.get("thumbnails") or [],
                    "thumbnail": entry.get("thumbnail"),
                }
            )
            if parsed:
                return parsed
    except Exception as e:
        print(f"[Youtube.search ytdlp] {e}", flush=True)
    return None


async def search(query: str) -> Optional[Dict[str, Any]]:
    if not query or not str(query).strip():
        return None

    q = str(query).strip()

    if "youtube.com" in q or "youtu.be" in q or (len(q) == 11 and " " not in q):
        vidid = _to_vidid(q)
        if vidid and len(vidid) >= 10:
            return {
                "title": "YouTube Video",
                "link": f"https://www.youtube.com/watch?v={vidid}",
                "vidid": vidid,
                "duration_min": "0:00",
                "thumbnail": f"https://i.ytimg.com/vi/{vidid}/hqdefault.jpg",
                "channel": "YouTube Music",
            }

    result = await _search_yts(q)
    if result:
        return result

    result = await _search_ytdlp(q)
    if result:
        return result

    print(f"[Youtube.search] No results for: {q}", flush=True)
    return None


def _safe_remove(path: str):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _clean_partials(vidid: str):
    try:
        if not os.path.isdir(DOWNLOAD_DIR):
            return
        for name in os.listdir(DOWNLOAD_DIR):
            if not name.startswith(vidid):
                continue
            lower = name.lower()
            if lower.endswith(".part") or lower.endswith(".ytdl") or ".part." in lower:
                _safe_remove(os.path.join(DOWNLOAD_DIR, name))
    except Exception:
        pass


def _ytdlp_base_opts(safe_mode: bool = False) -> dict:
    concurrent = 1 if safe_mode else 8
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": concurrent,
        "http_chunk_size": 10485760 if not safe_mode else 5242880,
        "buffersize": 1024 * 1024 * 16,
        "nocheckcertificate": True,
        "continuedl": False,
        "no_part": True,
        "overwrites": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb", "tv", "web"],
            }
        },
    }


def _is_416_error(text: str) -> bool:
    t = (text or "").lower()
    return (
        "416" in t
        or "requested range not satisfiable" in t
        or "range not satisfiable" in t
    )


async def _download_api(
    vidid: str, media_type: str, ext: str, timeout_total: int
) -> Optional[str]:
    vidid = _to_vidid(vidid)
    if not vidid or len(vidid) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{vidid}.{ext}")
    loop = asyncio.get_event_loop()

    lock = _get_lock(file_path)
    await lock.acquire()
    try:
        return await _download_api_locked(
            vidid, media_type, ext, timeout_total, file_path, loop
        )
    finally:
        lock.release()


async def _download_api_locked(
    vidid: str, media_type: str, ext: str, timeout_total: int, file_path: str, loop
) -> Optional[str]:
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
            dur = await loop.run_in_executor(None, check_duration, file_path)
            ok = dur and dur > 2
            if ok and media_type == "video":
                ok = await loop.run_in_executor(None, has_video_stream, file_path)
            if ok:
                return file_path
            _safe_remove(file_path)
    except Exception:
        pass

    if not API_KEY:
        print("[Youtube] API_KEY missing — API download skip", flush=True)
        return None

    full_url = f"https://www.youtube.com/watch?v={vidid}"
    url_variants = [full_url, vidid]
    type_variants = [media_type]
    if media_type == "video":
        type_variants = ["video", "mp4", "Video"]

    for attempt in range(3):
        use_url = url_variants[attempt % len(url_variants)]
        use_type = type_variants[attempt % len(type_variants)]
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_total, connect=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{API_URL.rstrip('/')}/download",
                    params={
                        "url": use_url,
                        "type": use_type,
                        "api_key": API_KEY,
                    },
                ) as resp:

                    if resp.status == 429:
                        wait = min(12, 2 * (attempt + 1))
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after and str(retry_after).isdigit():
                            wait = float(retry_after)
                        print(
                            f"[Youtube] {use_type} 429 — wait {wait}s (try {attempt+1})",
                            flush=True,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status in (500, 502, 503, 504):
                        body = (await resp.text())[:400]
                        if _is_416_error(body):
                            print(
                                f"[Youtube] {use_type} HTTP 416 from API — skip API, use local yt-dlp",
                                flush=True,
                            )
                            return None
                        wait = min(8, 2 ** attempt)
                        print(
                            f"[Youtube] {use_type} HTTP {resp.status}: {body} "
                            f"(try {attempt+1}, wait {wait}s)",
                            flush=True,
                        )
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        body = (await resp.text())[:250]
                        if _is_416_error(body):
                            print(
                                f"[Youtube] {use_type} 416 response — skip API",
                                flush=True,
                            )
                            return None
                        print(
                            f"[Youtube] {use_type} HTTP {resp.status}: {body} "
                            f"(try {attempt+1})",
                            flush=True,
                        )
                        await asyncio.sleep(1)
                        continue

                    with open(file_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(262144):
                            f.write(chunk)

            if not (os.path.exists(file_path) and os.path.getsize(file_path) > 1024):
                await asyncio.sleep(0.5)
                continue

            dur = await loop.run_in_executor(None, check_duration, file_path)
            if not (dur and dur > 2):
                print(
                    f"[Youtube] {use_type} invalid duration ({dur}s) — retry",
                    flush=True,
                )
                _safe_remove(file_path)
                await asyncio.sleep(1)
                continue

            if media_type == "video":
                has_v = await loop.run_in_executor(None, has_video_stream, file_path)
                print(
                    f"[Youtube] API video file size={os.path.getsize(file_path)} "
                    f"has_video={has_v}",
                    flush=True,
                )
                if not has_v:
                    _safe_remove(file_path)
                    if attempt >= 1:
                        return None
                    await asyncio.sleep(0.5)
                    continue

            return file_path

        except asyncio.TimeoutError:
            print(f"[Youtube] {use_type} timeout (try {attempt+1})", flush=True)
            _safe_remove(file_path)
        except Exception as e:
            print(
                f"[Youtube] {use_type} error (try {attempt+1}): {e}",
                flush=True,
            )
            _safe_remove(file_path)

        await asyncio.sleep(1)

    print(f"[Youtube] {media_type} API FAILED for {vidid}", flush=True)
    return None


def _find_downloaded(vidid: str, exts: tuple) -> Optional[str]:
    for name in os.listdir(DOWNLOAD_DIR):
        if name.startswith(vidid) and name.endswith(exts):
            path = os.path.join(DOWNLOAD_DIR, name)
            try:
                if os.path.getsize(path) > 1024:
                    return path
            except Exception:
                continue
    return None


async def _download_ytdlp_video(vidid: str) -> Optional[str]:
    try:
        import yt_dlp
    except Exception as e:
        print(f"[Youtube] yt-dlp not available: {e}", flush=True)
        return None

    vidid = _to_vidid(vidid)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{vidid}.%(ext)s")
    final_path = os.path.join(DOWNLOAD_DIR, f"{vidid}.mp4")

    lock = _get_lock(final_path)
    await lock.acquire()

    _clean_partials(vidid)

    format_attempts: List[str] = [
        "best[height<=720][ext=mp4]/best[height<=480][ext=mp4]/best[ext=mp4]/best",
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "bestvideo+bestaudio/best",
        "best",
        "18/22/best",
    ]

    def _run(fmt: str, safe_mode: bool = False):
        opts = _ytdlp_base_opts(safe_mode=safe_mode)
        opts.update(
            {
                "format": fmt,
                "outtmpl": out_tmpl,
                "merge_output_format": "mp4",
            }
        )
        url = f"https://www.youtube.com/watch?v={vidid}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
            return final_path

        path = _find_downloaded(vidid, (".mp4", ".mkv", ".webm"))
        if path and path.endswith(".mp4") and path != final_path:
            try:
                os.replace(path, final_path)
                return final_path
            except Exception:
                return path
        return path

    try:
        print(f"[Youtube] yt-dlp video download for {vidid}...", flush=True)
        last_err = None
        for fmt in format_attempts:
            for safe in (False, True):
                try:
                    _clean_partials(vidid)
                    path = await asyncio.to_thread(_run, fmt, safe)
                    if path and has_video_stream(path):
                        print(
                            f"[Youtube] yt-dlp OK path={path} size={os.path.getsize(path)} "
                            f"fmt={fmt[:40]} safe={safe}",
                            flush=True,
                        )
                        return path
                    if path:
                        print("[Youtube] yt-dlp file has no video stream — try next", flush=True)
                        _safe_remove(path)
                    break
                except Exception as e:
                    last_err = e
                    err = str(e)
                    print(f"[Youtube] yt-dlp video fail: {err[:180]}", flush=True)
                    if _is_416_error(err) and not safe:
                        print("[Youtube] 416 detected — retry same fmt in safe mode", flush=True)
                        continue
                    if "format is not available" in err.lower() or "requested format" in err.lower():
                        break
                    break

        print(f"[Youtube] yt-dlp video all formats failed: {last_err}", flush=True)
        return None
    except Exception as e:
        print(f"[Youtube] yt-dlp video error: {e}", flush=True)
        return None
    finally:
        lock.release()


async def _download_ytdlp_audio(vidid: str) -> Optional[str]:
    try:
        import yt_dlp
    except Exception as e:
        print(f"[Youtube] yt-dlp not available: {e}", flush=True)
        return None

    vidid = _to_vidid(vidid)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{vidid}.%(ext)s")
    final_path = os.path.join(DOWNLOAD_DIR, f"{vidid}.mp3")

    lock = _get_lock(final_path)
    await lock.acquire()

    _clean_partials(vidid)

    format_attempts: List[str] = [
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "140/251/250/249/bestaudio/best",
        "bestaudio/best",
        "bestaudio*",
        "best",
    ]

    def _run(fmt: str, extract_mp3: bool, safe_mode: bool = False):
        opts = _ytdlp_base_opts(safe_mode=safe_mode)
        opts.update(
            {
                "format": fmt,
                "outtmpl": out_tmpl,
            }
        )
        if extract_mp3:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        url = f"https://www.youtube.com/watch?v={vidid}"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
            return final_path

        return _find_downloaded(vidid, (".mp3", ".m4a", ".webm", ".opus", ".ogg"))

    try:
        print(f"[Youtube] yt-dlp audio download for {vidid}...", flush=True)
        last_err = None

        for fmt in format_attempts:
            for safe in (False, True):
                try:
                    _clean_partials(vidid)
                    path = await asyncio.to_thread(_run, fmt, False, safe)
                    if path:
                        print(
                            f"[Youtube] yt-dlp audio OK (raw) path={path} "
                            f"size={os.path.getsize(path)} safe={safe}",
                            flush=True,
                        )
                        return path
                except Exception as e:
                    last_err = e
                    err = str(e)
                    print(f"[Youtube] yt-dlp audio raw fail: {err[:180]}", flush=True)
                    if _is_416_error(err) and not safe:
                        print("[Youtube] 416 — retry audio in safe mode", flush=True)
                        continue
                    break

        for fmt in format_attempts:
            for safe in (False, True):
                try:
                    _clean_partials(vidid)
                    path = await asyncio.to_thread(_run, fmt, True, safe)
                    if path:
                        print(
                            f"[Youtube] yt-dlp audio OK path={path} "
                            f"size={os.path.getsize(path)} safe={safe}",
                            flush=True,
                        )
                        return path
                except Exception as e:
                    last_err = e
                    err = str(e)
                    print(f"[Youtube] yt-dlp audio fmt fail: {err[:180]}", flush=True)
                    if _is_416_error(err) and not safe:
                        continue
                    break

        print(f"[Youtube] yt-dlp audio all formats failed: {last_err}", flush=True)
        return None
    except Exception as e:
        print(f"[Youtube] yt-dlp audio error: {e}", flush=True)
        return None
    finally:
        lock.release()


def cached_file(vidid: str, is_video: bool) -> Optional[str]:
    """Optional local cache lookup used by stream.py."""
    vidid = _to_vidid(vidid)
    if not vidid or not os.path.isdir(DOWNLOAD_DIR):
        return None
    exts = (".mp4", ".mkv", ".webm") if is_video else (".mp3", ".m4a", ".webm", ".opus", ".ogg")
    for name in os.listdir(DOWNLOAD_DIR):
        if not name.startswith(vidid) or not name.endswith(exts):
            continue
        path = os.path.join(DOWNLOAD_DIR, name)
        try:
            if os.path.getsize(path) > 1024:
                if is_video and not has_video_stream(path):
                    continue
                if check_duration(path) > 2:
                    return path
        except Exception:
            continue
    return None


async def download_song(vidid: str) -> Optional[str]:
    try:
        path = await _download_api(vidid, "audio", "mp3", 80)
        if path:
            return path

        print(f"[Youtube] API audio failed — trying local yt-dlp for {vidid}", flush=True)
        return await _download_ytdlp_audio(vidid)
    except Exception as e:
        print(f"[Youtube.download_song] {e}", flush=True)
        return None


async def download_video(vidid: str) -> Optional[str]:
    try:
        path = await _download_api(vidid, "video", "mp4", 150)
        if path and has_video_stream(path):
            return path

        if path:
            print(
                "[Youtube] API returned file without video — trying yt-dlp",
                flush=True,
            )
            _safe_remove(path)

        path = await _download_ytdlp_video(vidid)
        return path
    except Exception as e:
        print(f"[Youtube.download_video] {e}", flush=True)
        return None
