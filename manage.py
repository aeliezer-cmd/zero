#!/usr/bin/env python3
"""Explicit local administration; filesystem access is required."""
import argparse, getpass, json
import app

p=argparse.ArgumentParser(description='Administración local de Zero')
sub=p.add_subparsers(dest='command',required=True)
sub.add_parser('list',help='Listar empresas y usuarios')
a=sub.add_parser('company',help='Crear empresa independiente')
a.add_argument('name');a.add_argument('--group',default='');a.add_argument('--demo',action='store_true')
a=sub.add_parser('grant',help='Autorizar usuario existente en otra empresa')
a.add_argument('username');a.add_argument('company_id',type=int);a.add_argument('--role',choices=app.ROLES,default='register');a.add_argument('--role-name',default='Colaborador');a.add_argument('--collections',action='store_true')
a=sub.add_parser('reset-password',help='Restablecer contraseña sin mostrarla');a.add_argument('username')
args=p.parse_args()
app.initialize()
with app.connect() as c:
    if args.command=='list':
        print('EMPRESAS');print(json.dumps(app.rows(c,'SELECT * FROM companies'),ensure_ascii=False,indent=2))
        print('USUARIOS');print(json.dumps(app.rows(c,'SELECT id,username,name FROM users'),ensure_ascii=False,indent=2))
    elif args.command=='company':
        ident=c.execute('INSERT INTO companies(name,demo,group_name) VALUES(?,?,?)',(app.text(args.name),int(args.demo),args.group)).lastrowid
        app.audit(c,None,ident,'crear','companies',ident,{'name':args.name,'group':args.group})
        print('Empresa creada:',ident)
    elif args.command=='grant':
        user=app.one(c,'SELECT * FROM users WHERE username=?',(args.username,));company=app.one(c,'SELECT * FROM companies WHERE id=?',(args.company_id,))
        if not user or not company: p.error('Usuario o empresa no encontrado.')
        c.execute('INSERT INTO memberships(user_id,company_id,role,role_name,collections) VALUES(?,?,?,?,?) ON CONFLICT(user_id,company_id) DO UPDATE SET role=excluded.role,role_name=excluded.role_name,collections=excluded.collections,departments=\'[]\',projects=\'[]\'',(user['id'],company['id'],args.role,args.role_name,int(args.collections)))
        app.audit(c,None,company['id'],'autorizar acceso local','memberships',user['id'],{'role':args.role,'collections':args.collections})
        print('Acceso autorizado. El grupo por sí solo nunca concede acceso.')
    elif args.command=='reset-password':
        pwd=getpass.getpass('Nueva contraseña (mínimo 12 caracteres): ')
        if len(pwd)<12: p.error('Contraseña demasiado corta.')
        if pwd!=getpass.getpass('Repita la contraseña: '): p.error('No coinciden.')
        cur=c.execute('UPDATE users SET password=? WHERE username=?',(app.password_hash(pwd),args.username))
        if not cur.rowcount: p.error('Usuario no encontrado.')
        print('Contraseña actualizada. Reinicie el servidor para cerrar sesiones previas.')
