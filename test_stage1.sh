#!/usr/bin/env bash
# Демонстрация логики Этапа 1 — все YAML создаются в каталоге tests/

set -e
set -u

echo "=== Тестирование Этапа 1 ==="

# Каталоги
mkdir -p tests/repo
mkdir -p out

# 1. Валидный конфиг
echo "[1] Валидный config.yaml"
cat > tests/config.yaml <<'YAML'
package_name: "my-lib"
repo_mode: "local"
repo: "./tests/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML
python depgraph.py -c tests/config.yaml
echo

# 2. Отсутствие config.yaml
echo "[2] Отсутствие config.yaml"
python depgraph.py -c tests/no_file.yaml || true
echo

# 3. Ошибка синтаксиса YAML
echo "[3] Ошибка синтаксиса YAML"
cat > tests/bad.yaml <<'YAML'
package_name: [
YAML
python depgraph.py -c tests/bad.yaml || true
echo

# 4. Отсутствующие ключи
echo "[4] Отсутствующие ключи"
cat > tests/missing.yaml <<'YAML'
package_name: "x"
YAML
python depgraph.py -c tests/missing.yaml || true
echo

# 5. Некорректный package_name
echo "[5] Некорректный package_name"
cat > tests/bad_pkg.yaml <<'YAML'
package_name: "my lib!"
repo_mode: "local"
repo: "./tests/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML
python depgraph.py -c tests/bad_pkg.yaml || true
echo

# 6. Некорректный repo_mode
echo "[6] Некорректный repo_mode"
cat > tests/bad_mode.yaml <<'YAML'
package_name: "ok"
repo_mode: "git"
repo: "./tests/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML
python depgraph.py -c tests/bad_mode.yaml || true
echo

# 7. Неверный URL при repo_mode=url
echo "[7] repo_mode=url без http"
cat > tests/bad_url.yaml <<'YAML'
package_name: "ok"
repo_mode: "url"
repo: "example.com/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML
python depgraph.py -c tests/bad_url.yaml || true
echo

# 8. Некорректный локальный путь
echo "[8] Некорректный локальный путь"
cat > tests/bad_local.yaml <<'YAML'
package_name: "ok"
repo_mode: "local"
repo: "./no_parent_dir_xxx/repo"
output_image: "./out/graph.png"
max_depth: 5
YAML
python depgraph.py -c tests/bad_local.yaml || true
echo

# 9. Неподдерживаемое расширение выходного файла
echo "[9] Неподдерживаемое расширение output_image"
cat > tests/bad_ext.yaml <<'YAML'
package_name: "ok"
repo_mode: "local"
repo: "./tests/repo"
output_image: "./out/graph.bmp"
max_depth: 5
YAML
python depgraph.py -c tests/bad_ext.yaml || true
echo

# 10. Некорректный max_depth
echo "[10] max_depth вне диапазона"
cat > tests/bad_depth.yaml <<'YAML'
package_name: "ok"
repo_mode: "local"
repo: "./tests/repo"
output_image: "./out/graph.png"
max_depth: 0
YAML
python depgraph.py -c tests/bad_depth.yaml || true
echo

echo "=== Тест завершён ==="