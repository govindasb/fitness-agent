from pydantic import BaseModel

from models.activity import ParsedActivity
from models.body_metric import ParsedBodyMetric
from models.food import ParsedFoodEntry
from models.sleep import ParsedSleep
from models.workout import ParsedWorkout


class ParsedInput(BaseModel):
    body_metrics: list[ParsedBodyMetric] = []
    food_entries: list[ParsedFoodEntry] = []
    workouts: list[ParsedWorkout] = []
    activities: list[ParsedActivity] = []
    sleep_entries: list[ParsedSleep] = []