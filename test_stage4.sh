#!/usr/bin/env bash
# Демонстрация Этапа 4: порядок загрузки зависимостей (топологический), итеративно, без рекурсии.

set -e
set -u

echo "=== Тестирование Этапа 4 ==="

mkdir -p tests
mkdir -p out

# 1) Простой DAG
#   A -> B, C
#   B -> D
#   C -> D, E
#   D ->
#   E ->
echo "[1] Простой DAG: зависимости раньше зависящих"
cat > tests/repo_stage4_simple.txt <<'TXT'
A: B C
B: D
C: D E
D:
E:
TXT

cat > tests/config_stage4_simple.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_stage4_simple.txt"
output_image: "./out/graph.png"
max_depth: 10
YAML

python depgraph.py -c tests/config_stage4_simple.yaml --load-order
echo

# 2) Общая зависимость и максимальная глубина
#   A -> B
#   B -> C
#   C -> D
#   D ->
echo "[2] Ограничение max_depth=2"
cat > tests/repo_stage4_depth.txt <<'TXT'
A: B
B: C
C: D
D:
TXT

cat > tests/config_stage4_depth.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_stage4_depth.txt"
output_image: "./out/graph.png"
max_depth: 2
YAML

python depgraph.py -c tests/config_stage4_depth.yaml --load-order
echo

# 3) Цикл: A->B->C->A
echo "[3] Циклический граф — топологический порядок невозможен (выводим частичный + список циклов)"
cat > tests/repo_stage4_cycle.txt <<'TXT'
A: B
B: C
C: A
TXT

cat > tests/config_stage4_cycle.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_stage4_cycle.txt"
output_image: "./out/graph.png"
max_depth: 10
YAML

python depgraph.py -c tests/config_stage4_cycle.yaml --load-order
echo

echo "=== Тестирование Этапа 4 завершено ==="