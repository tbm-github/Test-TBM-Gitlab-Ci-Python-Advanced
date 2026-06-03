from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import database
from main import app
import models

# Тестовая база данных в памяти
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Глобальные переменные для тестов
test_engine = None
TestingAsyncSession = None


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Создаем тестовую базу данных в памяти один раз для всех тестов"""
    global test_engine, TestingAsyncSession

    # Создаём тестовый engine (база в памяти)
    test_engine = create_async_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )

    # Создаём все таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(models.Recipe.metadata.create_all)

    # Создаём сессию
    TestingAsyncSession = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    yield

    # Очистка после всех тестов
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clear_tables():
    """Очищаем таблицы перед каждым тестом"""
    async with test_engine.begin() as conn:
        # Удаляем все данные из таблицы
        await conn.execute(models.Recipe.__table__.delete())
    yield


@pytest_asyncio.fixture
async def client():
    """HTTP-клиент для тестов с подменой зависимостей БД"""
    with (
        patch.object(database, "engine", test_engine),
        patch.object(database, "async_session", TestingAsyncSession),
    ):
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
        "description": "Тестовое описание",
    }
    response = await client.post("/recipes", json=recipe_data)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == recipe_data["title"]
    assert data["views"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_get_recipe_detail_increments_views(client):
    # Создаем рецепт
    resp_create = await client.post(
        "/recipes",
        json={
            "title": "Для просмотров",
            "cooking_time": 10,
            "ingredients": "инг",
            "description": "опис",
        },
    )
    assert resp_create.status_code == 201
    recipe_id = resp_create.json()["id"]
    assert resp_create.json()["views"] == 0

    # Первый просмотр
    resp1 = await client.get(f"/recipes/{recipe_id}")
    assert resp1.status_code == 200
    assert resp1.json()["views"] == 1

    # Второй просмотр
    resp2 = await client.get(f"/recipes/{recipe_id}")
    assert resp2.status_code == 200
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
