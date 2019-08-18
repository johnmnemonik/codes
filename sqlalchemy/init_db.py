import sqlalchemy as sa
from sqlalchemy import create_engine

metadata = sa.MetaData()
msg = "postgresql://{user}:{password}@{host}:{port}/{database}"
DSN = msg.format(user='john', password='loginn', host='localhost', port=5432, database='proj')
engine = create_engine(DSN, echo=True, isolation_level='AUTOCOMMIT')


# таблица локальных бек-коннект соксов
bc_auth = sa.Table(
	'bc_auth', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('login', sa.String(2000)),
	sa.Column('password', sa.String(255)),
	sa.Column('online', sa.Boolean),
	#sa.UniqueConstraint('ipreal', 'loc_port', 'ip', 'port', 'online')
	#sa.UniqueConstraint('loc_port', 'ipreal')
	)


bc = sa.Table(
	'bc', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	)


bc_ident = sa.Table(
	'bc_ident', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	sa.Column('ident', sa.String(2000), index=True, unique=True),
	#sa.UniqueConstraint('loc_port', 'ident')
	)

########################################################################
# эксперементальная потом нужно удалить
bc_1 = sa.Table(
	'bc_1', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	)

bc_2 = sa.Table(
	'bc_2', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	)

bc_ident_1 = sa.Table(
	'bc_ident_1', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	sa.Column('ident', sa.String(2000), index=True, unique=True),
	#sa.UniqueConstraint('loc_port', 'ident')
	)

bc_ident_2 = sa.Table(
	'bc_ident_2', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('loc_ip', sa.String(500), index=True),
	sa.Column('loc_port', sa.Integer, index=True, unique=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True, unique=True),
	sa.Column('allow', sa.String(2000)),
	sa.Column('online', sa.Boolean),
	sa.Column('ident', sa.String(2000), index=True, unique=True),
	#sa.UniqueConstraint('loc_port', 'ident')
	)
######################################################################


# таблица соксов со связью на bc
socks = sa.Table(
	'socks', metadata,
	sa.Column('id', sa.Integer, primary_key=True),
	sa.Column('ip', sa.String(500), index=True),
	sa.Column('port', sa.Integer, index=True),
	sa.Column('ipreal', sa.String(500), index=True),
	#sa.Column('bc_id', sa.Integer, sa.ForeignKey('bc.id')),
	)


def do_create_db(engine):
	conn = engine.connect()
	conn.execute("DROP DATABASE IF EXISTS socks")
	#conn.execute("CREATE DATABASE socks ENCODING 'UTF8'")
	#conn.execute("connect proj")
	#conn.execute("CREATE EXTENSION pgcrypto")
	conn.close()


def do_create_tables(engine):
	conn = engine.connect()
	conn.execute("DROP TABLE IF EXISTS socks CASCADE")
	conn.execute("DROP TABLE IF EXISTS users CASCADE")
	conn.execute("DROP TABLE IF EXISTS address CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_auth CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_ident CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_ident_1 CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_ident_2 CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_1 CASCADE")
	conn.execute("DROP TABLE IF EXISTS bc_2 CASCADE")
	conn.close()



def create_tables(engine):
	metadata.create_all(bind=engine, tables=[bc, bc_auth, bc_ident, bc_1, bc_2, bc_ident_1, bc_ident_2])



if __name__ == '__main__':
	do_create_tables(engine)
	create_tables(engine)