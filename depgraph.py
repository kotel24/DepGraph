from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any
import argparse, sys, os, re
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

# ----------------------------- CLI -----------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="depgraph",
        description="Этап 1: минимальный CLI — читает YAML-конфиг, валидирует и печатает параметры."
    )
    p.add_argument("-c", "--config", required=True, help="Путь к YAML-файлу конфигурации.")
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

    # Требование Этапа 1: вывести все настраиваемые параметры в формате ключ=значение.
    print("package_name=", cfg.package_name, sep="")
    print("repo=", cfg.repo, sep="")
    print("repo_mode=", cfg.repo_mode, sep="")
    print("output_image=", cfg.output_image, sep="")
    print("max_depth=", cfg.max_depth, sep="")
    return 0

# ----------------------------- Точка входа -----------------------------
if __name__ == "__main__":
    sys.exit(main())