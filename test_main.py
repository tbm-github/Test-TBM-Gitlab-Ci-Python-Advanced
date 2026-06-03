import asyncio
import os

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Импорты для main и database
import database
from main import app
import models

# Тестовая база данных
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_cookbook.db"
TEST_DB_FILE = "./test_cookbook.db"

# Удаляем старый файл если есть
if os.path.exists(TEST_DB_FILE):
    os.remove(TEST_DB_FILE)

# Создаем engine
test_engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)


# Функция для создания таблиц
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(models.Recipe.metadata.create_all)


# Запускаем создание таблиц синхронно
asyncio.run(create_tables())

# Создаем session
TestingAsyncSession = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

# Подменяем зависимости в модуле database
database.engine = test_engine
database.async_session = TestingAsyncSession


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def clear_tables():
    """Очищаем таблицы перед каждым тестом"""
    async with test_engine.begin() as conn:
        # Удаляем все данные
        await conn.execute(models.Recipe.__table__.delete())
    yield


@pytest_asyncio.fixture
async def client():
    """HTTP-клиент для тестов"""
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


# Очистка после всех тестов
def teardown_module():
    """Удаляем тестовую базу данных после всех тестов"""
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
