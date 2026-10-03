#!/bin/sh
# 找可用的 Python 執行 hook；都不能用就安靜放行（exit 0），不干擾寫檔。
# 要實際跑得起來才採用：Windows 的 python3／python 常是 Microsoft Store 的空殼別名，
# `command -v` 找得到，執行卻只印錯誤。探測時接 /dev/null，不吃掉要交給 hook 的 stdin。
DIR=$(dirname "$0")
for PY in python3 python; do
  if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import sys; sys.exit(sys.version_info[0] < 3)' </dev/null >/dev/null 2>&1; then
    exec "$PY" "$DIR/zhtw_post_write.py"
  fi
done
exit 0
