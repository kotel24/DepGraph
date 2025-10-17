#!/usr/bin/env bash
# Демонстрация Этапа 3: итеративный DFS (без рекурсии), max_depth, циклы, тестовый репозиторий (local).

set -e
set -u

echo "=== Тестирование Этапа 3 ==="

mkdir -p tests
mkdir -p out

# 1) Простой ациклический граф
#   A -> B, C
#   B -> D
#   C -> D, E
#   D ->
#   E ->
echo "[1] Простой граф (без циклов), max_depth=3"
cat > tests/repo_graph_simple.txt <<'TXT'
# формат: NODE: DEP1 DEP2 ...
A: B C
B: D
C: D E
D:
E:
TXT

cat > tests/config_stage3_simple.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_graph_simple.txt"
output_image: "./out/graph.png"
max_depth: 3
YAML

python depgraph.py -c tests/config_stage3_simple.yaml --analyze
echo

# 2) Граф с циклом
#   A -> B
#   B -> C
#   C -> A, D
#   D ->
echo "[2] Граф с циклом A->B->C->A, max_depth=5"
cat > tests/repo_graph_cycle.txt <<'TXT'
A: B
B: C
C: A D
D:
TXT

cat > tests/config_stage3_cycle.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_graph_cycle.txt"
output_image: "./out/graph.png"
max_depth: 5
YAML

python depgraph.py -c tests/config_stage3_cycle.yaml --analyze
echo

# 3) Ограничение глубины (обрезание)
#   A -> B
#   B -> C
#   C -> D
#   D ->
echo "[3] Проверка ограничения глубины: max_depth=2 (D не должен появиться)"
cat > tests/repo_graph_depth.txt <<'TXT'
A: B
B: C
C: D
D:
TXT

cat > tests/config_stage3_depth.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_graph_depth.txt"
output_image: "./out/graph.png"
max_depth: 2
YAML

python depgraph.py -c tests/config_stage3_depth.yaml --analyze
echo

# 4) (необязательно) URL-режим — пример анализа реального индекса Alpine
#    Включены виртуальные зависимости для наглядности. Этот шаг зависит от сети/SSL.
echo "[4] URL-режим (пример): git из community, max_depth=2, include_virtual"
cat > tests/config_stage3_url.yaml <<'YAML'
package_name: "git"
repo_mode: "url"
repo: "https://dl-cdn.alpinelinux.org/alpine/v3.20/community/x86_64"
output_image: "./out/graph.png"
max_depth: 2
YAML

python depgraph.py -c tests/config_stage3_url.yaml --analyze --include-virtual || true
echo

echo "=== Тестирование Этапа 3 завершено ==="