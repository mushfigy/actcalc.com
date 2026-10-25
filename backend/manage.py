"""Operator CLI: run from the app directory, with environment variables configured."""
from __future__ import annotations
import argparse, json
from .config import Settings
from . import db, mailer, backup

def main():
 p=argparse.ArgumentParser(description='ACTCalc server administration')
 p.add_argument('command',choices=['check','inbox','send','purge','backup','verify-backup','restore-as-new'])
 p.add_argument('paths',nargs='*',help='Backup destination, file to verify, or source and new database target')
 args=p.parse_args()
 cfg=Settings.from_env()
 if args.command=='check':
  print('Launch ready:',cfg.ready)
  for e in cfg.errors():print('-',e)
  if not cfg.ready:raise SystemExit(2)
  return
 if args.command in ('backup','verify-backup','restore-as-new'):
  required={'backup':1,'verify-backup':1,'restore-as-new':2}[args.command]
  if len(args.paths)!=required:p.error(f'{args.command} expects {required} path(s)')
  paths=[__import__('pathlib').Path(x).expanduser().resolve() for x in args.paths]
  if args.command=='backup':print('Private backup created; contacts:',backup.backup(cfg.db_path,paths[0]))
  elif args.command=='verify-backup':print('Database integrity verified; contacts:',backup.verify(paths[0]))
  else:print('Restored into new, inactive database; contacts:',backup.restore_as_new(paths[0],paths[1]))
  return
 db.initialize(cfg.db_path)
 if args.command=='inbox':
  # Do not echo secrets, but assume console access is restricted to the operator.
  for entry in db.list_contacts(cfg.db_path):print(json.dumps(entry,ensure_ascii=False))
 elif args.command=='send':print(mailer.send_batch(cfg))
 elif args.command=='purge':print('Expired contacts deleted:',db.purge(cfg.db_path))
if __name__=='__main__':main()
