import ipaddress
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from .auth import Auth
from .common import DB, owned, data, check_version
from .db import Product, StoredFile, now

router = APIRouter(prefix='/api')


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    summary: str = Field(default='', max_length=10000)
    internal_notes: str = Field(default='', max_length=20000)
    demo_url: str = Field(default='', max_length=2000)

    @field_validator('demo_url')
    @classmethod
    def safe_url(cls, value):
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ''
            if parsed.scheme != 'https' or not host or parsed.username or parsed.password or parsed.port not in (None, 443) or '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
                raise ValueError('请填写公开HTTPS演示地址')
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError('请使用公开演示域名')
            return value
        except (ValueError, TypeError) as exc:
            raise ValueError('演示地址无效') from exc


class Publish(BaseModel):
    version: int = Field(ge=1)
    approved: bool


@router.get('/products')
def products(db: DB, user: Auth):
    result = []
    for row in db.scalars(select(Product).where(Product.owner_id == user.id).order_by(Product.updated_at.desc())):
        files = db.scalars(select(StoredFile).where(StoredFile.product_id == row.id).order_by(StoredFile.created_at.desc())).all()
        result.append(dict(data(row), files=[data(f, ('storage_key', 'extracted_text')) for f in files]))
    return result


@router.post('/products', status_code=201)
def create_product(body: ProductCreate, db: DB, user: Auth):
    row = Product(owner_id=user.id, **body.model_dump())
    db.add(row)
    db.flush()
    return data(row)


@router.patch('/products/{product_id}')
def update_product(product_id: str, body: ProductCreate, version: int, db: DB, user: Auth):
    row = owned(db, Product, product_id, user)
    check_version(row, version)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.published = False
    row.updated_at = now()
    db.flush()
    return data(row)


@router.post('/products/{product_id}/publish')
def publish(product_id: str, body: Publish, db: DB, user: Auth):
    row = owned(db, Product, product_id, user)
    check_version(row, body.version)
    if not body.approved:
        raise HTTPException(422, '请确认资料和演示已脱敏')
    if not row.summary:
        raise HTTPException(422, '请填写产品介绍')
    row.published = True
    row.updated_at = now()
    db.flush()
    return data(row)


@router.post('/products/{product_id}/unpublish')
def unpublish(product_id: str, body: Publish, db: DB, user: Auth):
    row = owned(db, Product, product_id, user)
    check_version(row, body.version)
    row.published = False
    row.updated_at = now()
    db.flush()
    return data(row)


@router.get('/showcase')
def showcase(db: DB, user: Auth):
    result = []
    for row in db.scalars(select(Product).where(Product.owner_id == user.id, Product.published.is_(True)).order_by(Product.updated_at.desc())):
        pdfs = db.scalars(select(StoredFile).where(StoredFile.product_id == row.id, StoredFile.mime == 'application/pdf').order_by(StoredFile.created_at.desc())).all()
        result.append({'id': row.id, 'name': row.name, 'summary': row.summary, 'demo_url': row.demo_url, 'version': row.version, 'files': [{'id': f.id, 'name': f.name} for f in pdfs]})
    return result
