from sqlalchemy import Column, Integer, String

from database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    cooking_time = Column(Integer, nullable=False)  # минуты
    views = Column(Integer, default=0, nullable=False)
    # можно хранить как текст, разделитель - новая строка
    ingredients = Column(String, nullable=False)
    description = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Recipe {self.title}>"
