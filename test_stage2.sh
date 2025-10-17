#!/usr/bin/env bash
# Демонстрация логики Этапа 2 — загрузка и вывод прямых зависимостей из APKINDEX (Alpine Linux)

set -e
set -u

echo "=== Тестирование Этапа 2 ==="

# Подготовка каталогов
mkdir -p tests
mkdir -p out

# 1. Валидный конфиг с пакетом, у которого есть зависимости
echo "[1] Валидный config_stage2.yaml (пример с git)"
cat > tests/config_stage2.yaml <<'YAML'
package_name: "git"
repo_mode: "url"
repo: "https://dl-cdn.alpinelinux.org/alpine/v3.20/main/x86_64"
output_image: "./out/graph.png"
max_depth: 5
YAML

echo "---- Выполнение depgraph.py ----"
python depgraph.py -c tests/config_stage2.yaml
echo


# 2. Проверка обработки ошибки загрузки (неверный URL)
echo "[2] Ошибка загрузки APKINDEX (404)"
cat > tests/bad_repo.yaml <<'YAML'
package_name: "git"
repo_mode: "url"
repo: "https://example.com/nonexistent/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML

python depgraph.py -c tests/bad_repo.yaml || true
echo

# 3. Проверка неверного режима (local вместо url)
echo "[3] Ошибка — repo_mode=local (Stage 2 требует url)"
cat > tests/local_mode.yaml <<'YAML'
package_name: "git"
repo_mode: "local"
repo: "./tests/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML

python depgraph.py -c tests/local_mode.yaml || true
echo

echo "=== Тестирование Этапа 2 завершено ==="