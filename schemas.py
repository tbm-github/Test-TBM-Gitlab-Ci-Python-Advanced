from pydantic import BaseModel, ConfigDict


class RecipeBase(BaseModel):
    title: str
    cooking_time: int
    ingredients: str
    description: str


class RecipeCreate(RecipeBase):
    pass


class RecipeListItem(BaseModel):
    id: int
    title: str
    views: int
    cooking_time: int
    model_config = ConfigDict(from_attributes=True)


class RecipeDetail(RecipeBase):
    id: int
    views: int
    model_config = ConfigDict(from_attributes=True)
