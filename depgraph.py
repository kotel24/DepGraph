from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any, List
import argparse, sys, os, re, io, tarfile, urllib.request
import yaml

# ----------------------------- Ошибки -----------------------------
class MultipleConfigErrors(Exception):
    """Агрегирует все ошибки валидации за один проход."""
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Configuration has errors:\n" + "\n".join(f"- {e}" for e in errors))

# ----------------------------- Модель -----------------------------
RepoMode = Literal["url", "local"]

@dataclass
class Config:
    package_name: str           # Имя анализируемого пакета
    repo: str                   # URL репозитория или локальный путь (в зависимости от режима)
    repo_mode: RepoMode         # "url" | "local" — режим работы с тестовым репозиторием
    output_image: str           # Имя/путь итогового файла изображения графа
    max_depth: int              # Максимальная глубина анализа

    # --- Загрузка из YAML ---
    @staticmethod
    def from_yaml(path: str) -> "Config":
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error: {e}")
        return Config._validate_and_build(data)

    # --- Валидация ---
    @staticmethod
    def _validate_and_build(data: Dict[str, Any]) -> "Config":
        errors = []

        def require(key: str):
            if key not in data:
                errors.append(f"Missing required key '{key}'.")
                return None
            return data.get(key)

        package_name = require("package_name")
        repo        = require("repo")
        repo_mode   = require("repo_mode")
        output_img  = require("output_image")
        max_depth   = require("max_depth")

        # package_name
        if isinstance(package_name, str):
            if not package_name.strip():
                errors.append("package_name must be a non-empty string.")
            if not re.fullmatch(r"[A-Za-z0-9._\-]+", package_name or ""):
                errors.append("package_name may contain only letters, digits, '.', '_' or '-'.")
        else:
            errors.append("package_name must be a string.")

        # repo_mode
        if repo_mode not in ("url", "local"):
            errors.append("repo_mode must be either 'url' or 'local'.")

        # repo
        if isinstance(repo, str):
            if repo_mode == "url":
                if not re.match(r"^https?://", repo or ""):
                    errors.append("repo must start with 'http://' or 'https://' when repo_mode='url'.")
            elif repo_mode == "local":
                try:
                    p = os.path.abspath(os.path.expanduser(repo))
                    parent = os.path.dirname(p)
                    if not os.path.exists(p) and not os.path.isdir(parent):
                        errors.append("repo path parent directory does not exist for repo_mode='local'.")
                except Exception as e:
                    errors.append(f"repo path error for repo_mode='local': {e}")
        else:
            errors.append("repo must be a string.")

        # output_image
        valid_exts = {".png", ".svg", ".jpg", ".jpeg"}
        if isinstance(output_img, str):
            ext = os.path.splitext(output_img)[1].lower()
            if ext not in valid_exts:
                errors.append(f"output_image must have one of extensions: {', '.join(sorted(valid_exts))}.")
            out_path = os.path.abspath(os.path.expanduser(output_img))
            out_dir  = os.path.dirname(out_path) or os.getcwd()
            if not os.path.exists(out_dir):
                errors.append(f"Directory for output_image does not exist: {out_dir}")
            elif not os.access(out_dir, os.W_OK):
                errors.append(f"No write permission to directory: {out_dir}")
        else:
            errors.append("output_image must be a string path.")

        # max_depth
        if isinstance(max_depth, int):
            if not (1 <= max_depth <= 20):
                errors.append("max_depth must be an integer between 1 and 20.")
        else:
            errors.append("max_depth must be an integer.")

        if errors:
            raise MultipleConfigErrors(errors)

        return Config(
            package_name=package_name.strip(),
            repo=repo.strip(),
            repo_mode=repo_mode,
            output_image=output_img.strip(),
            max_depth=max_depth
        )

# ----------------------------- Этап 2: прямые зависимости из Alpine -----------------------------
def _index_url(repo_url: str) -> str:
    u = repo_url.strip()
    return u if u.endswith("/APKINDEX.tar.gz") else u.rstrip("/") + "/APKINDEX.tar.gz"

def _fetch_apkindex(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for m in tar.getmembers():
            if os.path.basename(m.name) == "APKINDEX":
                f = tar.extractfile(m)
                if not f:
                    raise RuntimeError("Cannot extract APKINDEX file")
                return f.read()
    raise RuntimeError("APKINDEX not found inside archive")

def _parse_apkindex(b: bytes) -> Dict[str, List[str]]:
    text = b.decode("utf-8", errors="replace")
    out: Dict[str, List[str]] = {}
    for block in [e for e in text.split("\n\n") if e.strip()]:
        pkg, deps = None, []
        for line in block.splitlines():
            if line.startswith("P:"):
                pkg = line[2:].strip()
            elif line.startswith("D:"):
                toks = line[2:].split()
                clean = []
                for t in toks:
                    if ":" in t:            # so:, cmd:, pc: — игнорируем
                        continue
                    name = re.split(r"[<>=~]", t, maxsplit=1)[0]
                    if re.fullmatch(r"[A-Za-z0-9._+\-]+", name or ""):
                        clean.append(name)
                deps = clean
        if pkg:
            out[pkg] = deps
    return out

def print_direct_dependencies(repo_url: str, package_name: str) -> int:
    try:
        idx = _fetch_apkindex(_index_url(repo_url))
    except Exception as e:
        print(f"[error] Failed to download APKINDEX: {e}", file=sys.stderr)
        return 1
    mapping = _parse_apkindex(idx)
    deps = mapping.get(package_name, [])
    # Требование Этапа 2: вывести все прямые зависимости
    for d in deps:
        print(d)
    if not deps:
        print("(none)")
    return 0

# ----------------------------- CLI -----------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="depgraph",
        description="Этап 2: сбор данных зависимостей (Alpine APKINDEX)."
    )
    p.add_argument("-c", "--config", required=True, help="Путь к YAML-файлу конфигурации.")
    p.add_argument("--echo-config", action="store_true",
                   help="Опционально: повторить поведение Этапа 1 (вывести параметры ключ=значение).")
    return p.parse_args(argv)

def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        cfg = Config.from_yaml(args.config)
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2
    except MultipleConfigErrors as e:
        print("[error] Invalid configuration:", file=sys.stderr)
        for line in e.errors:
            print(" -", line, file=sys.stderr)
        return 3
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    # (необязательно) Этап 1-поведение — только если явно попросили
    if args.echo_config:
        print("package_name=", cfg.package_name, sep="")
        print("repo=", cfg.repo, sep="")
        print("repo_mode=", cfg.repo_mode, sep="")
        print("output_image=", cfg.output_image, sep="")
        print("max_depth=", cfg.max_depth, sep="")

    # Этап 2 — обязательно: печатаем прямые зависимости указанного пакета (для URL-репозитория)
    if cfg.repo_mode != "url":
        print("[error] Stage 2 expects repo_mode='url' with an Alpine repository URL.", file=sys.stderr)
        return 1

    return print_direct_dependencies(cfg.repo, cfg.package_name)

# ----------------------------- Точка входа -----------------------------
if __name__ == "__main__":
    sys.exit(main())