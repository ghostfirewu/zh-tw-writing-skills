#!/bin/sh
# 找可用的 Python 執行 hook；兩者都沒有就安靜放行（exit 0），不干擾寫檔。
DIR=$(dirname "$0")
if command -v python3 >/dev/null 2>&1; then exec python3 "$DIR/zhtw_post_write.py"; fi
if command -v python >/dev/null 2>&1; then exec python "$DIR/zhtw_post_write.py"; fi
exit 0
