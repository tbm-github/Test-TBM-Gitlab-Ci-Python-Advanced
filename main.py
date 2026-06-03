from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from sqlalchemy import select

from database import async_session, engine
import models
import schemas


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(models.Recipe.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(title="Кулинарная книга API", lifespan=lifespan)


@app.get("/recipes", response_model=List[schemas.RecipeListItem])
async def list_recipes():
    async with async_session() as session:
        stmt = select(models.Recipe).order_by(
            models.Recipe.views.desc(), models.Recipe.cooking_time.asc()
        )
        result = await session.execute(stmt)
        recipes = result.scalars().all()
        return recipes


@app.get("/recipes/{recipe_id}", response_model=schemas.RecipeDetail)
async def get_recipe(recipe_id: int):
    async with async_session() as session:
        stmt = select(models.Recipe).where(models.Recipe.id == recipe_id)
        result = await session.execute(stmt)
        recipe = result.scalar_one_or_none()
        if not recipe:
            raise HTTPException(status_code=404, detail="Рецепт не найден")
        recipe.views += 1
        session.add(recipe)
        await session.commit()
        await session.refresh(recipe)
        return recipe


@app.post("/recipes", response_model=schemas.RecipeDetail, status_code=201)
async def create_recipe(recipe_data: schemas.RecipeCreate):
    async with async_session() as session:
        new_recipe = models.Recipe(
            title=recipe_data.title,
            cooking_time=recipe_data.cooking_time,
            ingredients=recipe_data.ingredients,
            description=recipe_data.description,
            views=0,
        )
        session.add(new_recipe)
        await session.commit()
        await session.refresh(new_recipe)
        return new_recipe
