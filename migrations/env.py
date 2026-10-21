import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config,pool
from dotenv import load_dotenv
from server.db import Base

load_dotenv()
config=context.config
url=config.attributes.get('database_url') or os.getenv('DATABASE_URL',config.get_main_option('sqlalchemy.url'))
config.set_main_option('sqlalchemy.url',url.replace('%','%%'))
if context.is_offline_mode():
    context.configure(url=url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction():context.run_migrations()
else:
    engine=engine_from_config(config.get_section(config.config_ini_section),prefix='sqlalchemy.',poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()
