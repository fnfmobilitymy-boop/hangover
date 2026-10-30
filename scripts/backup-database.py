"""Consistent SQLite backup. Store the output securely; it contains customer data."""
import argparse
import os
import sqlite3
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('output',type=Path)
parser.add_argument('--database',type=Path,default=Path(os.environ.get('KENNY_DATA_DIR','.data'))/'kenny.sqlite3')
args=parser.parse_args()
if args.output.exists():
    raise SystemExit('Refusing to overwrite an existing backup')
if not args.database.is_file():
    raise SystemExit('Database not found')
fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.close(fd)
with sqlite3.connect(args.database) as source, sqlite3.connect(args.output) as target:
    source.backup(target)
print('Database backup completed')
