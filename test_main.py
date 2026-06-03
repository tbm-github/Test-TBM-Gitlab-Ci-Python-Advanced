import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from main import app
from database import Base
import models
import database

# Тестовая база данных – используем отдельный файл
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_cookbook.db"
TEST_DB_FILE = "./test_cookbook.db"

# Удаляем старый файл, если он остался с предыдущих запусков
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

# Создаём тестовый engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

TestingAsyncSession = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Перед каждым тестом пересоздаём таблицы (полная очистка)"""
    async with test_engine.begin() as conn:
        await conn.run_sync(models.Recipe.metadata.drop_all)
        await conn.run_sync(models.Recipe.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client(setup_db):
    """HTTP-клиент с подменой зависимостей БД на тестовые"""
    with patch.object(database, "engine", test_engine), \
         patch.object(database, "async_session", TestingAsyncSession):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------- Тесты ----------
@pytest.mark.asyncio
async def test_create_recipe(client):
    recipe_data = {
        "title": "Тестовый рецепт",
        "cooking_time": 30,
        "ingredients": "Тестовые ингредиенты",
        "description": "Тестовое описание"
    }
    response = await client.post("/recipes", json=recipe_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == recipe_data["title"]
    assert data["views"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_get_recipe_detail_increments_views(client):
    resp_create = await client.post("/recipes", json={
        "title": "Для просмотров", "cooking_time": 10,
        "ingredients": "инг", "description": "опис"
    })
    recipe_id = resp_create.json()["id"]
    assert resp_create.json()["views"] == 0

    resp1 = await client.get(f"/recipes/{recipe_id}")
    assert resp1.status_code == 200
    assert resp1.json()["views"] == 1

    resp2 = await client.get(f"/recipes/{recipe_id}")
    assert resp2.json()["views"] == 2


@pytest.mark.asyncio
async def test_get_nonexistent_recipe_returns_404(client):
    response = await client.get("/recipes/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Рецепт не найден"


@pytest.mark.asyncio
async def test_create_recipe_missing_fields(client):
    incomplete_data = {"title": "Без времени"}
    response = await client.post("/recipes", json=incomplete_data)
    assert response.status_code == 422