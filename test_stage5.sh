#!/usr/bin/env bash
# Демонстрация Этапа 5: визуализация (Mermaid + PNG) для трех разных пакетов

set -e
set -u

echo "=== Тестирование Этапа 5 ==="

mkdir -p tests
mkdir -p out

# Тестовый граф с тремя различными стартовыми пакетами: A, X, M
cat > tests/repo_stage5.txt <<'TXT'
# Общий файл тестового графа
# Подграф 1
A: B C
B: D
C: D E
D:
E:

# Подграф 2
X: Y Z
Y: Z
Z:

# Подграф 3 (с ветвлением)
M: N O
N: P
O:
P:
TXT

# 1) A (max_depth=3)
echo "[1] Визуализация для A (max_depth=3)"
cat > tests/config_stage5_A.yaml <<'YAML'
package_name: "A"
repo_mode: "local"
repo: "./tests/repo_stage5.txt"
output_image: "./out/graph_A.png"
max_depth: 3
YAML
python depgraph.py -c tests/config_stage5_A.yaml --viz --dir=LR
echo

# 2) X (max_depth=5)
echo "[2] Визуализация для X (max_depth=5)"
cat > tests/config_stage5_X.yaml <<'YAML'
package_name: "X"
repo_mode: "local"
repo: "./tests/repo_stage5.txt"
output_image: "./out/graph_X.png"
max_depth: 5
YAML
python depgraph.py -c tests/config_stage5_X.yaml --viz
echo

# 3) M (max_depth=2)
echo "[3] Визуализация для M (max_depth=2)"
cat > tests/config_stage5_M.yaml <<'YAML'
package_name: "M"
repo_mode: "local"
repo: "./tests/repo_stage5.txt"
output_image: "./out/graph_M.png"
max_depth: 2
YAML
python depgraph.py -c tests/config_stage5_M.yaml --viz
echo

echo "=== Тестирование Этапа 5 завершено ==="