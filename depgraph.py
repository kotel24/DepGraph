from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any, List, Tuple, Set
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
    repo: str                   # URL репозитория (url) или путь к файлу тестового графа (local)
    repo_mode: RepoMode         # "url" | "local"
    output_image: str           # Имя/путь итогового файла изображения графа (валидируем, но пока не используем)
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
            if not re.fullmatch(r"[A-Za-z0-9._\\-]+", package_name or ""):
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

# ----------------------------- Этап 2: прямые зависимости (APKINDEX) -----------------------------
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

def _parse_apkindex(b: bytes, include_virtual: bool = False) -> Dict[str, List[str]]:
    """
    Парсит APKINDEX в {pkg: [deps]}.
    include_virtual=False — игнорируем виртуальные so:/cmd:/pc:, оставляя только «обычные» пакетные имена.
    """
    text = b.decode("utf-8", errors="replace")
    out: Dict[str, List[str]] = {}
    for block in [e for e in text.split("\n\n") if e.strip()]:
        pkg, deps = None, []
        for line in block.splitlines():
            if line.startswith("P:"):
                pkg = line[2:].strip()
            elif line.startswith("D:"):
                toks = line[2:].split()
                buf: List[str] = []
                for t in toks:
                    if ":" in t:            # so:, cmd:, pc:
                        if include_virtual:
                            buf.append(t.strip())
                        continue
                    name = re.split(r"[<>=~]", t, maxsplit=1)[0]
                    if re.fullmatch(r"[A-Za-z0-9._+\-]+", name or ""):
                        buf.append(name)
                deps = buf
        if pkg:
            out[pkg] = deps
    return out

def print_direct_dependencies(repo_url: str, package_name: str) -> int:
    try:
        idx = _fetch_apkindex(_index_url(repo_url))
    except Exception as e:
        print(f"[error] Failed to download APKINDEX: {e}", file=sys.stderr)
        return 1
    mapping = _parse_apkindex(idx, include_virtual=False)
    deps = mapping.get(package_name, [])
    for d in deps:
        print(d)
    if not deps:
        print("(none)")
    return 0

# ----------------------------- Этап 3: тестовый граф + итеративный DFS -----------------------------
def load_test_graph_from_file(path: str) -> Dict[str, List[str]]:
    """
    Тестовый режим (repo_mode=local).
    Формат файла (узлы — БОЛЬШИЕ латинские буквы):
      # комментарии
      A: B C
      B: D
      C:
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Test graph file not found: {path}")

    mapping: Dict[str, List[str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"Invalid line {lineno}: expected 'NODE: deps...'")
            left, right = line.split(":", 1)
            node = left.strip()
            if not re.fullmatch(r"[A-Z]+", node):
                raise ValueError(f"Invalid node name at line {lineno}: '{node}', expected A..Z")
            deps = [t for t in right.strip().split() if t]
            for d in deps:
                if not re.fullmatch(r"[A-Z]+", d):
                    raise ValueError(f"Invalid dependency name at line {lineno}: '{d}', expected A..Z")
            mapping[node] = deps

    # Добавим пустые записи для узлов, встречающихся только как зависимости
    for vlist in list(mapping.values()):
        for v in vlist:
            mapping.setdefault(v, [])
    return mapping

def build_full_graph_from_url(repo_url: str, include_virtual: bool = False) -> Dict[str, List[str]]:
    """Строит граф {pkg: deps} из APKINDEX (по умолчанию без виртуальных зависимостей)."""
    idx = _fetch_apkindex(_index_url(repo_url))
    return _parse_apkindex(idx, include_virtual=include_virtual)

def iterative_dfs(mapping: Dict[str, List[str]], start: str, max_depth: int
                  ) -> Tuple[Set[Tuple[str, str]], List[str], List[List[str]]]:
    """
    Итеративный DFS (без рекурсии) с ограничением глубины.
    Возвращает:
      edges  — множество рёбер (u, v)
      order  — порядок первого посещения вершин
      cycles — список циклов, каждый как список узлов, замыкающийся в начало
    """
    if start not in mapping:
        return set(), [], []

    edges: Set[Tuple[str, str]] = set()
    order: List[str] = []
    cycles: List[List[str]] = []

    # Кадр стека: (node, depth, next_child_index)
    stack: List[Tuple[str, int, int]] = [(start, 0, 0)]
    on_path: List[str] = []
    on_path_set: Set[str] = set()
    best_depth: Dict[str, int] = {}  # минимальная достигнутая глубина для узла

    while stack:
        node, depth, idx = stack.pop()

        if idx == 0:
            # вход в вершину
            if node not in best_depth:
                best_depth[node] = depth
                order.append(node)
            elif depth >= best_depth[node]:
                continue
            else:
                best_depth[node] = depth

            on_path.append(node)
            on_path_set.add(node)

        neighbors = mapping.get(node, [])
        if depth < max_depth and idx < len(neighbors):
            nei = neighbors[idx]
            edges.add((node, nei))
            # вернём текущий кадр с переходом к следующему соседу
            stack.append((node, depth, idx + 1))

            if nei in on_path_set:
                # нашли цикл: от nei до текущего конца on_path + возврат к nei
                try:
                    k = on_path.index(nei)
                    cycles.append(on_path[k:] + [nei])
                except ValueError:
                    pass
                continue

            if nei not in best_depth or depth + 1 < best_depth[nei]:
                stack.append((nei, depth + 1, 0))
        else:
            # выход из вершины
            if on_path and on_path[-1] == node:
                on_path.pop()
                on_path_set.discard(node)

    return edges, order, cycles

def print_graph_analysis(mapping: Dict[str, List[str]], start: str, max_depth: int) -> None:
    edges, order, cycles = iterative_dfs(mapping, start, max_depth)

    print(f"# dependency_graph (max_depth={max_depth})")
    if edges:
        for u, v in sorted(edges):
            print(f"{u} -> {v}")
    else:
        print("(no edges)")

    print("\n# order")
    print(" -> ".join(order) if order else "(empty)")

    print("\n# cycles")
    if cycles:
        for cyc in cycles:
            print(" -> ".join(cyc))
    else:
        print("(none)")

# ----------------------------- Этап 4: порядок загрузки (топологический) -----------------------------
def compute_load_order(mapping: Dict[str, List[str]], start: str, max_depth: int
                       ) -> Tuple[List[str], List[List[str]]]:
    """
    Возвращает порядок загрузки зависимостей (зависимости раньше зависящих).
    Итеративный DFS без рекурсии, учитываем max_depth.
    Если есть циклы — возвращаем частичный порядок (reverse postorder) и список циклов.
    """
    if start not in mapping:
        return [], []

    load_order: List[str] = []        # reverse postorder (без дублей)
    seen: Set[str] = set()
    on_path: Set[str] = set()
    cycles: List[List[str]] = []

    # стек кадров: (node, depth, idx, state) ; state=0 -> enter, 1 -> exit
    stack: List[Tuple[str, int, int, int]] = [(start, 0, 0, 0)]
    path: List[str] = []

    # чтобы не зависеть от порядка ключей dict, фиксируем порядок соседей как в списке
    while stack:
        node, depth, idx, state = stack.pop()

        if state == 0:
            if node in on_path:
                # цикл — найдём путь из node в текущем path
                try:
                    k = path.index(node)
                    cycles.append(path[k:] + [node])
                except ValueError:
                    pass
                continue
            if node not in seen:
                seen.add(node)
                on_path.add(node)
                path.append(node)

                # планируем выходной шаг
                stack.append((node, depth, 0, 1))

                # раскрываем соседей
                neighbors = mapping.get(node, [])
                if depth < max_depth:
                    # добавляем в стек в обратном порядке, чтобы первый сосед обрабатывался первым
                    for nei in reversed(neighbors):
                        stack.append((nei, depth + 1, 0, 0))
            # иначе: уже обработан и в load_order (или будет при выходе)
        else:
            # выход из вершины: добавляем в load_order
            if path and path[-1] == node:
                path.pop()
            on_path.discard(node)
            if node not in load_order:
                load_order.append(node)

    # в load_order сейчас *зависимости раньше зависящих*, так как мы добавляем «на выходе» (postorder)
    return load_order, cycles

def print_load_order(mapping: Dict[str, List[str]], start: str, max_depth: int) -> None:
    order, cycles = compute_load_order(mapping, start, max_depth)

    print(f"# load_order (max_depth={max_depth})")
    if order:
        # как правило, последним будет стартовый пакет
        print(" -> ".join(order))
    else:
        print("(empty)")

    print("\n# cycles")
    if cycles:
        for cyc in cycles:
            print(" -> ".join(cyc))
    else:
        print("(none)")

# ----------------------------- CLI -----------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="depgraph",
        description=("Этап 4: вывод порядка загрузки зависимостей (топологический порядок). "
                     "Этап 3: анализ графа (--analyze). Этап 2: прямые зависимости (URL). "
                     "Этап 1: --echo-config печатает параметры ключ=значение.")
    )
    p.add_argument("-c", "--config", required=True, help="Путь к YAML-файлу конфигурации.")
    p.add_argument("--echo-config", action="store_true",
                   help="(Опционально) Повторить поведение Этапа 1 — вывести параметры ключ=значение.")
    p.add_argument("--analyze", action="store_true",
                   help="Построить ПОЛНЫЙ граф зависимостей и вывести рёбра/порядок/циклы (Этап 3).")
    p.add_argument("--include-virtual", action="store_true",
                   help="Для URL-режима включать виртуальные зависимости (so:, cmd:, pc:) при анализе графа.")
    p.add_argument("--load-order", action="store_true",
                   help="(Только для Этапа 4) Вывести порядок загрузки зависимостей для заданного пакета.")
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

    # Этап 1 — по флагу
    if args.echo_config:
        print("package_name=", cfg.package_name, sep="")
        print("repo=", cfg.repo, sep="")
        print("repo_mode=", cfg.repo_mode, sep="")
        print("output_image=", cfg.output_image, sep="")
        print("max_depth=", cfg.max_depth, sep="")
        print()

    # Подготовим граф в зависимости от режима и флагов
    mapping: Dict[str, List[str]]

    if cfg.repo_mode == "local":
        try:
            mapping = load_test_graph_from_file(os.path.expanduser(cfg.repo))
        except Exception as e:
            print(f"[error] Failed to load test graph: {e}", file=sys.stderr)
            return 1
    else:  # url
        if args.analyze or args.load_order:
            try:
                mapping = build_full_graph_from_url(cfg.repo, include_virtual=args.include_virtual)
            except Exception as e:
                print(f"[error] Failed to build graph from APKINDEX: {e}", file=sys.stderr)
                return 1
        else:
            # Этап 2: только прямые зависимости
            return print_direct_dependencies(cfg.repo, cfg.package_name)

    # Этап 4: если попросили порядок загрузки — печатаем его и выходим
    if args.load_order:
        print_load_order(mapping, cfg.package_name, cfg.max_depth)
        return 0

    # Этап 3: анализ графа (рёбра/порядок посещения/циклы)
    if args.analyze:
        if cfg.package_name not in mapping:
            print(f"[warn] Start package '{cfg.package_name}' not found in repository graph.", file=sys.stderr)
        print_graph_analysis(mapping, cfg.package_name, cfg.max_depth)
        return 0

    # Если пользователь не указал ни --load-order, ни --analyze в local-режиме —
    # явно подскажем, что делать.
    if cfg.repo_mode == "local":
        print("[info] For local test graph use one of: --analyze (Stage 3) or --load-order (Stage 4).")
        return 0

    return 0

# ----------------------------- Точка входа -----------------------------
if __name__ == "__main__":
    sys.exit(main())