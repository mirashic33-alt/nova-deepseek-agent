"""
data/keystore.py — шифрованное хранилище секретов через Windows DPAPI.
Ключи привязаны к текущему пользователю Windows — на другом компе не расшифруются.
Файл: secrets/keys.enc в корне проекта.
"""
import os
import json
import ctypes
import ctypes.wintypes
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
KEYSTORE_PATH = ROOT_DIR / "secrets" / "keys.enc"

_crypt = ctypes.windll.crypt32
_kernel = ctypes.windll.kernel32


class _BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _dpapi_encrypt(data: bytes) -> bytes:
    blob_in = _BLOB(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _BLOB()
    if not _crypt.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise RuntimeError(f"CryptProtectData failed ({ctypes.GetLastError()})")
    result = bytes(ctypes.string_at(blob_out.pbData, blob_out.cbData))
    _kernel.LocalFree(blob_out.pbData)
    return result


def _dpapi_decrypt(data: bytes) -> bytes:
    blob_in = _BLOB(len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _BLOB()
    if not _crypt.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise RuntimeError(f"CryptUnprotectData failed ({ctypes.GetLastError()})")
    result = bytes(ctypes.string_at(blob_out.pbData, blob_out.cbData))
    _kernel.LocalFree(blob_out.pbData)
    return result


_session: dict = {}
_loaded = False


def load_if_exists() -> None:
    """Читаем и расшифровываем keys.enc в память (один раз при старте)."""
    global _session, _loaded
    if not KEYSTORE_PATH.exists():
        _migrate_from_env()
        _loaded = True
        return
    try:
        _session = json.loads(_dpapi_decrypt(KEYSTORE_PATH.read_bytes()))
    except Exception:
        _session = {}
    _loaded = True


def _migrate_from_env() -> None:
    """Если есть .env — мигрируем ключи в keystore и удаляем .env."""
    global _session, _loaded
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        _session = {}
        _loaded = True
        return
    _session = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            _session[k.strip()] = v.strip()
    if _session:
        _save_session()
        env_path.unlink()  # удаляем .env после миграции
    _loaded = True


def _save_session() -> None:
    KEYSTORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    KEYSTORE_PATH.write_bytes(_dpapi_encrypt(json.dumps(_session).encode()))


def get(key: str, default: str = "") -> str:
    if not _loaded:
        load_if_exists()
    return _session.get(key, default)


def set_key(key: str, value: str) -> None:
    """Записать секрет и сохранить зашифрованно."""
    global _session, _loaded
    if not _loaded:
        load_if_exists()
    _session[key] = value
    _save_session()
    _loaded = True
